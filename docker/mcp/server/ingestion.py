"""
Bulk code ingestion pipeline.

Walk a repo → AST-parse each supported file → chunk by function/method →
embed via Ollama → upsert into FalkorDB.  Zero LLM calls.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pathspec
from tree_sitter import Language, Node, Parser

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import tree_sitter_go as tsgo

# Tier 1 additions (graceful degradation if package absent)
def _try_import(mod):
    try:
        import importlib
        return importlib.import_module(mod)
    except ImportError:
        return None

_tsrust    = _try_import("tree_sitter_rust")
_tsjava    = _try_import("tree_sitter_java")
_tsc       = _try_import("tree_sitter_c")
_tscpp     = _try_import("tree_sitter_cpp")
_tscsharp  = _try_import("tree_sitter_c_sharp")
_tsruby    = _try_import("tree_sitter_ruby")
_tsphp     = _try_import("tree_sitter_php")
_tskotlin  = _try_import("tree_sitter_kotlin")
_tsswift   = _try_import("tree_sitter_swift")
_tsscala   = _try_import("tree_sitter_scala")
_tsbash    = _try_import("tree_sitter_bash")
_tslua     = _try_import("tree_sitter_lua")

from .config import config
from .db import get_graph
from .embedder import embed
from .schema import ensure_schema

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language registry
# ---------------------------------------------------------------------------

_PARSERS: dict[str, Parser] = {}


def _get_parser(ext: str) -> Parser | None:
    if ext in _PARSERS:
        return _PARSERS[ext]
    try:
        lang_obj = None
        if ext == "py":
            lang_obj = Language(tspython.language())
        elif ext in ("js", "jsx", "mjs", "cjs"):
            lang_obj = Language(tsjavascript.language())
        elif ext in ("ts", "mts"):
            lang_obj = Language(tstypescript.language_typescript())
        elif ext == "tsx":
            lang_obj = Language(tstypescript.language_tsx())
        elif ext == "go":
            lang_obj = Language(tsgo.language())
        elif ext == "rs" and _tsrust:
            lang_obj = Language(_tsrust.language())
        elif ext == "java" and _tsjava:
            lang_obj = Language(_tsjava.language())
        elif ext in ("c", "h") and _tsc:
            lang_obj = Language(_tsc.language())
        elif ext in ("cpp", "cc", "cxx", "hpp", "hxx") and _tscpp:
            lang_obj = Language(_tscpp.language())
        elif ext == "cs" and _tscsharp:
            lang_obj = Language(_tscsharp.language())
        elif ext == "rb" and _tsruby:
            lang_obj = Language(_tsruby.language())
        elif ext == "php" and _tsphp:
            lang_obj = Language(_tsphp.language_php() if hasattr(_tsphp, "language_php") else _tsphp.language())
        elif ext in ("kt", "kts") and _tskotlin:
            lang_obj = Language(_tskotlin.language())
        elif ext == "swift" and _tsswift:
            lang_obj = Language(_tsswift.language())
        elif ext in ("scala", "sc") and _tsscala:
            lang_obj = Language(_tsscala.language())
        elif ext in ("sh", "bash") and _tsbash:
            lang_obj = Language(_tsbash.language())
        elif ext == "lua" and _tslua:
            lang_obj = Language(_tslua.language())

        if lang_obj is None:
            return None
        p = Parser(lang_obj)
        _PARSERS[ext] = p
        return p
    except Exception as exc:
        log.warning("tree-sitter parser unavailable for .%s: %s", ext, exc)
        return None


# ---------------------------------------------------------------------------
# Chunk extraction
# ---------------------------------------------------------------------------

# Node types that represent a function/method across all supported languages
_FUNCTION_TYPES = {
    "function_definition",        # Python / C / C++ / Bash / Scala
    "async_function_definition",  # Python
    "function_declaration",       # JS/TS / Kotlin / Swift / Lua
    "function_expression",        # JS/TS
    "arrow_function",             # JS/TS (named via var)
    "method_definition",          # JS/TS class methods
    "method_declaration",         # Go / C# / PHP
    "function_literal",           # Go
    "function_item",              # Rust
    "constructor_declaration",    # Java / C#
    "method",                     # Ruby
    "singleton_method",           # Ruby
    "local_function_statement",   # Lua
    "def_definition",             # Scala
}

_CLASS_TYPES = {
    "class_definition",    # Python / Scala
    "class_declaration",   # JS/TS / Java / C# / PHP / Kotlin / Swift
    "type_declaration",    # Go (struct-like)
    "impl_item",           # Rust (method block for a type)
    "class_specifier",     # C++
    "struct_specifier",    # C++
    "interface_declaration", # Java / C# / PHP / Kotlin / Swift
    "module",              # Ruby
}

_NAME_FIELD = "name"


def _node_name(node: Node, ext: str = "") -> str:
    name_node = node.child_by_field_name(_NAME_FIELD)
    if name_node:
        return name_node.text.decode("utf-8", errors="replace")
    # C/C++: function_definition → declarator → function_declarator → declarator (identifier)
    if ext in ("c", "h", "cpp", "cc", "cxx", "hpp", "hxx") and node.type == "function_definition":
        decl = node.child_by_field_name("declarator")
        if decl:
            fn_decl = decl if decl.type == "function_declarator" else None
            if fn_decl is None:
                for child in decl.children:
                    if child.type == "function_declarator":
                        fn_decl = child
                        break
            if fn_decl:
                inner = fn_decl.child_by_field_name("declarator")
                if inner and inner.type == "identifier":
                    return inner.text.decode("utf-8", errors="replace")
    return "<anonymous>"


@dataclass
class Chunk:
    path: str
    symbol: str          # dotted: module.Class.method
    kind: str            # function | method | class
    lang: str
    signature: str       # first non-empty line of the node
    start_line: int      # 1-based
    end_line: int        # 1-based
    start_byte: int
    end_byte: int
    content: str         # raw text, used only for hashing + embedding, NOT stored in DB


def _extract_chunks(code: bytes, path: str, lang: str) -> list[Chunk]:
    parser = _get_parser(lang)
    if parser is None:
        return []
    tree = parser.parse(code)
    module = Path(path).stem
    chunks: list[Chunk] = []
    _walk(tree.root_node, code, path, lang, [module], chunks)
    return chunks


def _walk(
    node: Node,
    code: bytes,
    path: str,
    lang: str,
    parent_path: list[str],
    chunks: list[Chunk],
) -> None:
    if node.type in _FUNCTION_TYPES:
        name = _node_name(node, lang)
        kind = "method" if len(parent_path) > 1 else "function"
        symbol = ".".join(parent_path + [name])
        content = code[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
        content = _strip_noise(content)
        sig = _signature(content)
        chunks.append(
            Chunk(
                path=path,
                symbol=symbol,
                kind=kind,
                lang=lang,
                signature=sig,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                content=content,
            )
        )
        # Don't recurse — nested functions become separate symbols from their parent context.
        return

    if node.type in _CLASS_TYPES:
        name = _node_name(node)
        for child in node.children:
            _walk(child, code, path, lang, parent_path + [name], chunks)
        return

    for child in node.children:
        _walk(child, code, path, lang, parent_path, chunks)


_DECORATOR_LINE = re.compile(r"^[\s#/*\-=~`]{5,}\s*$")
_LICENSE_KW = re.compile(r"\b(copyright|license|spdx|mit|apache|gpl)\b", re.IGNORECASE)


def _strip_noise(text: str) -> str:
    """Remove decorative separator lines. Keep docstrings."""
    lines = text.splitlines()
    return "\n".join(l for l in lines if not _DECORATOR_LINE.match(l))


def _signature(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return ""


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _chunk_id(path: str, symbol: str) -> str:
    return hashlib.sha256(f"{path}::{symbol}".encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# .gitignore-aware file walker
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "vendor", ".mypy_cache",
}

_SKIP_EXTENSIONS = {
    ".lock", ".sum", ".mod", ".min.js", ".min.css",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz",
    ".pyc", ".pyo", ".so", ".dylib", ".dll",
}

_MAX_FILE_BYTES = 512 * 1024  # 512 KB


def _walk_repo(repo_path: str) -> Iterator[tuple[str, str]]:
    """Yield (absolute_path, extension) for every supported file, respecting .gitignore."""
    root = Path(repo_path)
    gitignore_file = root / ".gitignore"
    spec = pathspec.PathSpec.from_lines("gitwildmatch", gitignore_file.read_text().splitlines()
                                         if gitignore_file.exists() else [])

    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(root)
        if spec.match_file(str(rel)):
            continue
        ext = p.suffix.lstrip(".")
        if _get_parser(ext) is None:
            continue
        if any(str(p).endswith(s) for s in _SKIP_EXTENSIONS):
            continue
        if p.stat().st_size > _MAX_FILE_BYTES:
            continue
        yield str(p), ext


# ---------------------------------------------------------------------------
# FalkorDB upsert
# ---------------------------------------------------------------------------

def _upsert_chunk(group_id: str, chunk: Chunk) -> bool:
    """
    Insert or update a CodeChunk.  Returns True if a re-embed was performed.
    Hash-gated: skips embed if content_hash unchanged.
    """
    g = get_graph(group_id)
    cid = _chunk_id(chunk.path, chunk.symbol)
    chash = _content_hash(chunk.content)

    result = g.query(
        "MATCH (c:CodeChunk {id: $id}) RETURN c.content_hash AS h",
        {"id": cid},
    )
    existing_hash = result.result_set[0][0] if result.result_set else None

    if existing_hash == chash:
        return False

    vec = embed(chunk.content, purpose="code")
    now = int(time.time() * 1000)

    g.query(
        """
        MERGE (c:CodeChunk {id: $id})
        SET c.group_id      = $gid,
            c.path          = $path,
            c.symbol        = $symbol,
            c.kind          = $kind,
            c.lang          = $lang,
            c.signature     = $sig,
            c.start_line    = $sl,
            c.end_line      = $el,
            c.start_byte    = $sb,
            c.end_byte      = $eb,
            c.content_hash  = $chash,
            c.emb           = vecf32($emb),
            c.emb_model     = $model,
            c.emb_dim       = $dim,
            c.loc           = $loc,
            c.updated_at    = $now,
            c.indexed_at    = $now,
            c.valid         = true,
            c.created_at    = COALESCE(c.created_at, $now)
        """,
        {
            "id": cid,
            "gid": group_id,
            "path": chunk.path,
            "symbol": chunk.symbol,
            "kind": chunk.kind,
            "lang": chunk.lang,
            "sig": chunk.signature,
            "sl": chunk.start_line,
            "el": chunk.end_line,
            "sb": chunk.start_byte,
            "eb": chunk.end_byte,
            "chash": chash,
            "emb": vec,
            "model": config.CODE_EMBED_MODEL,
            "dim": len(vec),
            "loc": chunk.end_line - chunk.start_line + 1,
            "now": now,
        },
    )
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_repo(group_id: str, repo_path: str) -> dict:
    """
    Full bulk ingest for a project.  Idempotent and hash-gated.
    Called by SessionStart hook in background.
    """
    ensure_schema(group_id)
    total = embedded = skipped = errors = 0

    for file_path, ext in _walk_repo(repo_path):
        try:
            code = Path(file_path).read_bytes()
            chunks = _extract_chunks(code, file_path, ext)
            for chunk in chunks:
                total += 1
                try:
                    if _upsert_chunk(group_id, chunk):
                        embedded += 1
                    else:
                        skipped += 1
                except Exception as e:
                    log.warning("chunk upsert failed %s::%s — %s", file_path, chunk.symbol, e)
                    errors += 1
        except Exception as e:
            log.warning("file read/parse failed %s — %s", file_path, e)
            errors += 1

    # Mark last full scan and store repo_path for incremental graph updates
    g = get_graph(group_id)
    now = int(time.time() * 1000)
    g.query(
        "MATCH (p:Project {group_id: $gid}) SET p.last_full_scan_at = $now, p.repo_path = $repo",
        {"gid": group_id, "now": now, "repo": repo_path},
    )

    log.info("ingest done — total=%d embedded=%d skipped=%d errors=%d", total, embedded, skipped, errors)

    # Phase 5B — build call graph after all chunks are in the DB
    try:
        from .graph_builder import build_graph
        graph_stats = build_graph(group_id, repo_path)
        log.info("call graph built — %s", graph_stats)
    except Exception as exc:
        log.warning("call graph build failed (non-fatal): %s", exc)
        graph_stats = {}

    return {"total": total, "embedded": embedded, "skipped": skipped, "errors": errors,
            "graph": graph_stats}


def reindex_file(group_id: str, file_path: str) -> dict:
    """
    Incremental reindex for a single file (PostToolUse:Write/Edit).
    Only re-embeds chunks whose content_hash changed.
    """
    ensure_schema(group_id)
    ext = Path(file_path).suffix.lstrip(".")
    try:
        code = Path(file_path).read_bytes()
    except FileNotFoundError:
        # File was deleted — mark all its chunks invalid
        g = get_graph(group_id)
        now = int(time.time() * 1000)
        g.query(
            "MATCH (c:CodeChunk {path: $path}) SET c.valid = false, c.updated_at = $now",
            {"path": file_path, "now": now},
        )
        return {"deleted": True}

    chunks = _extract_chunks(code, file_path, ext)
    embedded = skipped = 0
    for chunk in chunks:
        if _upsert_chunk(group_id, chunk):
            embedded += 1
        else:
            skipped += 1

    # Invalidate symbols that no longer exist in this file
    surviving_ids = {_chunk_id(chunk.path, chunk.symbol) for chunk in chunks}
    g = get_graph(group_id)
    result = g.query(
        "MATCH (c:CodeChunk {path: $path, valid: true}) RETURN c.id",
        {"path": file_path},
    )
    now = int(time.time() * 1000)
    for row in result.result_set:
        if row[0] not in surviving_ids:
            g.query(
                "MATCH (c:CodeChunk {id: $id}) SET c.valid = false, c.updated_at = $now",
                {"id": row[0], "now": now},
            )

    # Phase 5B — incremental graph update for this file
    try:
        from .graph_builder import rebuild_file_graph
        # Retrieve repo_path stored on Project node during ingest
        _g = get_graph(group_id)
        _res = _g.query(
            "MATCH (p:Project {group_id: $gid}) RETURN p.repo_path LIMIT 1",
            {"gid": group_id},
        )
        _repo = _res.result_set[0][0] if _res.result_set else None
        if _repo:
            rebuild_file_graph(group_id, file_path, _repo)
    except Exception as exc:
        log.debug("incremental graph update skipped for %s: %s", file_path, exc)

    return {"embedded": embedded, "skipped": skipped}

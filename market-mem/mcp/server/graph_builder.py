"""
Call graph extraction and persistence (Phase 5B).

Extracts CALLS and IMPORTS edges from AST, resolves them to CodeChunk /
FileNode nodes in FalkorDB, and persists as graph edges.  Zero LLM.
Zero embedding.

Certitude-only policy: an edge is created only when the callee / import
target can be resolved with certainty.  Ambiguous or dynamic calls are
silently skipped — they are not errors.

Tier coverage
─────────────
  Tier 1 — Full (CALLS + IMPORTS): Python, JS, TS, Go, Rust, Java, C, C++, C#
  Tier 2 — Partial (best-effort static + IMPORTS): Ruby, PHP, Kotlin, Swift, Scala
  Tier 3 — IMPORTS only: Bash, Lua, Haskell, Elixir
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pathspec
from tree_sitter import Language, Node, Parser

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional language imports (graceful degradation if package missing)
# ---------------------------------------------------------------------------

def _try_import(module: str):
    try:
        import importlib
        return importlib.import_module(module)
    except ImportError:
        return None


_tspython     = _try_import("tree_sitter_python")
_tsjavascript = _try_import("tree_sitter_javascript")
_tstypescript = _try_import("tree_sitter_typescript")
_tsgo         = _try_import("tree_sitter_go")
_tsrust       = _try_import("tree_sitter_rust")
_tsjava       = _try_import("tree_sitter_java")
_tsc          = _try_import("tree_sitter_c")
_tscpp        = _try_import("tree_sitter_cpp")
_tscsharp     = _try_import("tree_sitter_c_sharp")
_tsruby       = _try_import("tree_sitter_ruby")
_tsphp        = _try_import("tree_sitter_php")
_tskotlin     = _try_import("tree_sitter_kotlin")
_tsswift      = _try_import("tree_sitter_swift")
_tsscala      = _try_import("tree_sitter_scala")
_tsbash       = _try_import("tree_sitter_bash")
_tslua        = _try_import("tree_sitter_lua")
_tshaskell    = _try_import("tree_sitter_haskell")
_tselixir     = _try_import("tree_sitter_elixir")

# ---------------------------------------------------------------------------
# Parser registry (shared with ingestion, but independent instance)
# ---------------------------------------------------------------------------

_PARSERS: dict[str, Parser] = {}


def _get_parser(ext: str) -> Parser | None:
    if ext in _PARSERS:
        return _PARSERS[ext]
    try:
        lang_obj = None
        if ext == "py" and _tspython:
            lang_obj = Language(_tspython.language())
        elif ext in ("js", "jsx", "mjs", "cjs") and _tsjavascript:
            lang_obj = Language(_tsjavascript.language())
        elif ext in ("ts", "mts") and _tstypescript:
            lang_obj = Language(_tstypescript.language_typescript())
        elif ext == "tsx" and _tstypescript:
            lang_obj = Language(_tstypescript.language_tsx())
        elif ext == "go" and _tsgo:
            lang_obj = Language(_tsgo.language())
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
            if hasattr(_tsphp, "language_php"):
                lang_obj = Language(_tsphp.language_php())
            else:
                lang_obj = Language(_tsphp.language())
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
        elif ext in ("hs", "lhs") and _tshaskell:
            lang_obj = Language(_tshaskell.language())
        elif ext in ("ex", "exs") and _tselixir:
            lang_obj = Language(_tselixir.language())

        if lang_obj is None:
            return None
        p = Parser(lang_obj)
        _PARSERS[ext] = p
        return p
    except Exception as exc:
        log.debug("tree-sitter parser unavailable for .%s: %s", ext, exc)
        return None


# ---------------------------------------------------------------------------
# Call node specifications
# ---------------------------------------------------------------------------
# Format: ext -> (call_node_type, name_field | None, accepted_id_types)
# name_field=None → use first child of type in accepted_id_types

_CALL_SPECS: dict[str, tuple[str, str | None, frozenset[str]]] = {
    "py":    ("call",                    "function",   frozenset({"identifier"})),
    "js":    ("call_expression",         "function",   frozenset({"identifier"})),
    "jsx":   ("call_expression",         "function",   frozenset({"identifier"})),
    "mjs":   ("call_expression",         "function",   frozenset({"identifier"})),
    "cjs":   ("call_expression",         "function",   frozenset({"identifier"})),
    "ts":    ("call_expression",         "function",   frozenset({"identifier"})),
    "tsx":   ("call_expression",         "function",   frozenset({"identifier"})),
    "mts":   ("call_expression",         "function",   frozenset({"identifier"})),
    "go":    ("call_expression",         "function",   frozenset({"identifier"})),
    "rs":    ("call_expression",         "function",   frozenset({"identifier"})),
    "java":  ("method_invocation",       "name",       frozenset({"identifier"})),
    "c":     ("call_expression",         "function",   frozenset({"identifier"})),
    "h":     ("call_expression",         "function",   frozenset({"identifier"})),
    "cpp":   ("call_expression",         "function",   frozenset({"identifier"})),
    "cc":    ("call_expression",         "function",   frozenset({"identifier"})),
    "cxx":   ("call_expression",         "function",   frozenset({"identifier"})),
    "hpp":   ("call_expression",         "function",   frozenset({"identifier"})),
    # tree-sitter-c-sharp: invocation_expression's callee field is "function"
    # (identifier for Foo(), member_access_expression for obj.Bar())
    "cs":    ("invocation_expression",   "function",   frozenset({"identifier"})),
    "rb":    ("call",                    "method",     frozenset({"identifier"})),
    "php":   ("function_call_expression","function",   frozenset({"name", "identifier"})),
    "kt":    ("call_expression",         None,         frozenset({"simple_identifier"})),
    "kts":   ("call_expression",         None,         frozenset({"simple_identifier"})),
    "swift": ("call_expression",         "function",   frozenset({"simple_identifier", "identifier"})),
    "lua":   ("function_call",           None,         frozenset({"identifier"})),
}

# Member-access callee nodes: when the call target is one of these node
# types, the terminal method name lives in the given field.
# Verified against the installed tree-sitter grammars (see probe in tests).
_MEMBER_SPECS: dict[str, dict[str, str]] = {
    "py":    {"attribute": "attribute"},                                    # self.bar() / a.b.c()
    "js":    {"member_expression": "property"},                             # obj.bar()
    "jsx":   {"member_expression": "property"},
    "mjs":   {"member_expression": "property"},
    "cjs":   {"member_expression": "property"},
    "ts":    {"member_expression": "property"},
    "tsx":   {"member_expression": "property"},
    "mts":   {"member_expression": "property"},
    "go":    {"selector_expression": "field"},                              # obj.Bar()
    "rs":    {"field_expression": "field", "scoped_identifier": "name"},    # obj.bar() / m::n()
    "c":     {"field_expression": "field"},                                 # s.bar() / p->baz()
    "h":     {"field_expression": "field"},
    "cpp":   {"field_expression": "field", "qualified_identifier": "name"}, # + ns::qux()
    "cc":    {"field_expression": "field", "qualified_identifier": "name"},
    "cxx":   {"field_expression": "field", "qualified_identifier": "name"},
    "hpp":   {"field_expression": "field", "qualified_identifier": "name"},
    "cs":    {"member_access_expression": "name"},                          # obj.Bar() / this.X.Qux()
    # java: method_invocation's "name" field is already the terminal
    # identifier even for obj.bar() — nothing extra needed.
}

# Node types accepted as the terminal method-name node of a member access.
_TERMINAL_ID_TYPES = frozenset({
    "identifier", "property_identifier", "field_identifier",
    "simple_identifier", "name",
})


def _extract_calls(fn_node: Node, ext: str) -> list[str]:
    """Return callee names called within *fn_node* body.

    Handles both bare identifiers (``foo()``) and member accesses
    (``obj.foo()`` / ``ptr->foo()`` / ``ns::foo()``) — for member accesses
    the terminal method name is extracted.
    """
    spec = _CALL_SPECS.get(ext)
    if not spec:
        return []
    call_type, name_field, id_types = spec
    member_spec = _MEMBER_SPECS.get(ext, {})

    results: list[str] = []

    def _target_name(target: Node) -> str | None:
        if target.type in id_types:
            return target.text.decode("utf-8", errors="replace").strip() or None
        field = member_spec.get(target.type)
        if field:
            name_node = target.child_by_field_name(field)
            if name_node and name_node.type in _TERMINAL_ID_TYPES:
                return name_node.text.decode("utf-8", errors="replace").strip() or None
        return None

    def _walk(n: Node) -> None:
        if n.type == call_type:
            if name_field:
                target = n.child_by_field_name(name_field)
                if target:
                    name = _target_name(target)
                    if name:
                        results.append(name)
            else:
                # Find the first child that yields a name (identifier or member)
                for child in n.children:
                    name = _target_name(child)
                    if name:
                        results.append(name)
                        break
        for child in n.children:
            _walk(child)

    _walk(fn_node)
    return results


# ---------------------------------------------------------------------------
# Import extraction (per-language)
# ---------------------------------------------------------------------------

@dataclass
class _ImportSpec:
    raw: str        # raw module / path string as it appears in source
    is_relative: bool = False


def _extract_imports(tree_root: Node, code: bytes, ext: str) -> list[_ImportSpec]:
    """Walk *tree_root* and return all import specs found in the file."""
    if ext == "py":
        return _imports_python(tree_root, code)
    if ext in ("js", "jsx", "mjs", "cjs", "ts", "tsx", "mts"):
        return _imports_js(tree_root, code)
    if ext == "go":
        return _imports_go(tree_root, code)
    if ext == "rs":
        return _imports_rust(tree_root, code)
    if ext == "java":
        return _imports_java(tree_root, code)
    if ext in ("c", "h", "cpp", "cc", "cxx", "hpp", "hxx"):
        return _imports_c(tree_root, code)
    if ext == "cs":
        return _imports_csharp(tree_root, code)
    if ext == "rb":
        return _imports_ruby(tree_root, code)
    if ext == "php":
        return _imports_php(tree_root, code)
    if ext in ("kt", "kts"):
        return _imports_kotlin(tree_root, code)
    if ext == "swift":
        return _imports_swift(tree_root, code)
    if ext in ("scala", "sc"):
        return _imports_scala(tree_root, code)
    if ext in ("sh", "bash"):
        return _imports_bash(tree_root, code)
    if ext == "lua":
        return _imports_lua(tree_root, code)
    if ext in ("hs", "lhs"):
        return _imports_haskell(tree_root, code)
    if ext in ("ex", "exs"):
        return _imports_elixir(tree_root, code)
    return []


def _text(node: Node, code: bytes) -> str:
    return code[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _walk_nodes(root: Node, target_type: str):
    """Yield all descendant nodes of *target_type*."""
    if root.type == target_type:
        yield root
    for child in root.children:
        yield from _walk_nodes(child, target_type)


def _imports_python(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in root.children:
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    specs.append(_ImportSpec(raw=_text(child, code)))
                elif child.type == "aliased_import":
                    dn = child.child_by_field_name("name")
                    if dn:
                        specs.append(_ImportSpec(raw=_text(dn, code)))
        elif node.type == "import_from_statement":
            # from <module> import <names>
            # module may be None for relative imports (from . import x)
            relative = False
            module = ""
            for child in node.children:
                if child.type in (".", ".."):
                    relative = True
                elif child.type == "dotted_name" and not module:
                    module = _text(child, code)
                elif child.type == "relative_import":
                    relative = True
                    dn = child.child_by_field_name("import")
                    if dn:
                        module = _text(dn, code)
            if module:
                specs.append(_ImportSpec(raw=module, is_relative=relative))
    return specs


def _imports_js(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "import_statement"):
        source = node.child_by_field_name("source")
        if source:
            raw = _text(source, code).strip("'\"`")
            specs.append(_ImportSpec(raw=raw, is_relative=raw.startswith(("./", "../"))))
    # require() calls: call_expression where function=identifier "require"
    for node in _walk_nodes(root, "call_expression"):
        fn = node.child_by_field_name("function")
        if fn and fn.type == "identifier" and _text(fn, code) == "require":
            args = node.child_by_field_name("arguments")
            if args and args.child_count >= 2:
                arg = args.children[1]
                if arg.type in ("string", "template_string"):
                    raw = _text(arg, code).strip("'\"`")
                    specs.append(_ImportSpec(raw=raw, is_relative=raw.startswith(("./", "../"))))
    return specs


def _imports_go(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "import_spec"):
        path = node.child_by_field_name("path")
        if path:
            raw = _text(path, code).strip('"')
            specs.append(_ImportSpec(raw=raw))
    return specs


def _imports_rust(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "use_declaration"):
        arg = node.child_by_field_name("argument")
        if arg:
            raw = _text(arg, code)
            # Only internal: crate:: or super:: or self::
            if raw.startswith(("crate::", "super::", "self::")):
                specs.append(_ImportSpec(raw=raw, is_relative=True))
    return specs


def _imports_java(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "import_declaration"):
        # import com.example.MyClass; or import static com.example.Cls.method;
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                specs.append(_ImportSpec(raw=_text(child, code)))
                break
    return specs


def _imports_c(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "preproc_include"):
        for child in node.children:
            if child.type == "string_literal":
                raw = _text(child, code).strip('"')
                specs.append(_ImportSpec(raw=raw, is_relative=True))
            # system_lib_string (<...>) → skip (external)
    return specs


def _imports_csharp(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "using_directive"):
        for child in node.children:
            if child.type in ("qualified_name", "identifier", "alias_qualified_name"):
                specs.append(_ImportSpec(raw=_text(child, code)))
                break
    return specs


def _imports_ruby(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    # require/require_relative are method calls
    for node in _walk_nodes(root, "call"):
        method = node.child_by_field_name("method")
        if method and _text(method, code) in ("require", "require_relative"):
            args = node.child_by_field_name("arguments")
            if args:
                for child in args.children:
                    if child.type in ("string", "simple_symbol"):
                        raw = _text(child, code).strip("'\":")
                        relative = _text(method, code) == "require_relative"
                        specs.append(_ImportSpec(raw=raw, is_relative=relative))
    return specs


def _imports_php(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for kind in ("include_expression", "include_once_expression",
                 "require_expression", "require_once_expression"):
        for node in _walk_nodes(root, kind):
            for child in node.children:
                if child.type in ("encapsed_string", "string"):
                    raw = _text(child, code).strip("'\"")
                    specs.append(_ImportSpec(raw=raw, is_relative=True))
    # use declarations
    for node in _walk_nodes(root, "namespace_use_declaration"):
        for child in _walk_nodes(node, "namespace_name"):
            specs.append(_ImportSpec(raw=_text(child, code)))
    return specs


def _imports_kotlin(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "import_header"):
        for child in node.children:
            if child.type in ("identifier", "dot_qualified_expression"):
                specs.append(_ImportSpec(raw=_text(child, code)))
                break
    return specs


def _imports_swift(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "import_declaration"):
        for child in node.children:
            if child.type in ("identifier", "dot_qualified_name"):
                specs.append(_ImportSpec(raw=_text(child, code)))
                break
    return specs


def _imports_scala(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "import_declaration"):
        for child in node.children:
            if child.type in ("stable_id", "import_expr"):
                specs.append(_ImportSpec(raw=_text(child, code)))
                break
    return specs


def _imports_bash(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "command"):
        name = node.child_by_field_name("name")
        if name and _text(name, code) == "source":
            for arg in node.children[1:]:
                if arg.type in ("word", "string"):
                    specs.append(_ImportSpec(raw=_text(arg, code).strip("'\""), is_relative=True))
    return specs


def _imports_lua(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "function_call"):
        # require("module")
        first = None
        for child in node.children:
            if child.type == "identifier":
                first = _text(child, code)
                break
        if first == "require":
            for child in node.children:
                if child.type == "arguments":
                    for arg in child.children:
                        if arg.type == "string":
                            raw = _text(arg, code).strip("'\"")
                            specs.append(_ImportSpec(raw=raw))
    return specs


def _imports_haskell(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "import"):
        module = node.child_by_field_name("module")
        if module:
            specs.append(_ImportSpec(raw=_text(module, code)))
    return specs


def _imports_elixir(root: Node, code: bytes) -> list[_ImportSpec]:
    specs = []
    for node in _walk_nodes(root, "call"):
        fn = node.child_by_field_name("target")
        if fn and _text(fn, code) in ("import", "alias", "use", "require"):
            args = node.child_by_field_name("arguments")
            if args:
                for child in args.children:
                    if child.type == "alias":
                        specs.append(_ImportSpec(raw=_text(child, code)))
    return specs


# ---------------------------------------------------------------------------
# Import → file path resolution
# ---------------------------------------------------------------------------

def _resolve_import(
    spec: _ImportSpec,
    source_file: str,
    ext: str,
    repo_root: str,
    all_paths: set[str],
) -> str | None:
    """Try to resolve an import spec to an absolute file path in the repo.
    Returns None when the import is external or ambiguous.
    """
    raw = spec.raw
    root = Path(repo_root)
    src_dir = Path(source_file).parent

    if ext == "py":
        return _resolve_python(raw, spec.is_relative, src_dir, root, all_paths)
    if ext in ("js", "jsx", "mjs", "cjs", "ts", "tsx", "mts"):
        return _resolve_js(raw, spec.is_relative, src_dir, root, all_paths)
    if ext in ("c", "h", "cpp", "cc", "cxx", "hpp", "hxx"):
        return _resolve_c_include(raw, src_dir, root, all_paths)
    if ext == "rs":
        return _resolve_rust(raw, src_dir, root, all_paths)
    if ext == "rb":
        return _resolve_ruby(raw, spec.is_relative, src_dir, root, all_paths)
    if ext in ("sh", "bash"):
        return _resolve_relative_path(raw, src_dir, root, all_paths)
    if ext == "php":
        if spec.is_relative:
            return _resolve_relative_path(raw, src_dir, root, all_paths)
    # Java, C#, Kotlin, Swift, Scala, Go: package-name resolution — skip for now
    # (reliable resolution requires module/project config)
    return None


def _resolve_python(
    raw: str, is_relative: bool, src_dir: Path, repo_root: Path, all_paths: set[str],
) -> str | None:
    parts = raw.replace(".", "/")
    candidates = [
        f"{parts}.py",
        f"{parts}/__init__.py",
    ]
    if is_relative:
        for c in candidates:
            p = (src_dir / c).resolve()
            if str(p) in all_paths:
                return str(p)
    else:
        for c in candidates:
            p = (repo_root / c).resolve()
            if str(p) in all_paths:
                return str(p)
    return None


def _resolve_js(
    raw: str, is_relative: bool, src_dir: Path, repo_root: Path, all_paths: set[str],
) -> str | None:
    if not is_relative:
        return None  # npm package, skip
    base = (src_dir / raw).resolve()
    # Try adding extensions
    for ext in ("", ".js", ".ts", ".jsx", ".tsx", "/index.js", "/index.ts"):
        p = Path(str(base) + ext)
        if str(p) in all_paths:
            return str(p)
    return None


def _resolve_c_include(
    raw: str, src_dir: Path, repo_root: Path, all_paths: set[str],
) -> str | None:
    # Relative includes first
    candidates = [
        (src_dir / raw).resolve(),
        (repo_root / raw).resolve(),
    ]
    for p in candidates:
        if str(p) in all_paths:
            return str(p)
    return None


def _resolve_rust(
    raw: str, src_dir: Path, repo_root: Path, all_paths: set[str],
) -> str | None:
    # crate::foo::bar → src/foo/bar.rs
    if raw.startswith("crate::"):
        parts = raw[len("crate::"):].replace("::", "/")
    elif raw.startswith("super::"):
        parts = "../" + raw[len("super::"):].replace("::", "/")
    elif raw.startswith("self::"):
        parts = raw[len("self::"):].replace("::", "/")
    else:
        return None
    candidates = [
        (repo_root / "src" / f"{parts}.rs").resolve(),
        (repo_root / "src" / parts / "mod.rs").resolve(),
    ]
    for p in candidates:
        if str(p) in all_paths:
            return str(p)
    return None


def _resolve_ruby(
    raw: str, is_relative: bool, src_dir: Path, repo_root: Path, all_paths: set[str],
) -> str | None:
    base = raw if raw.endswith(".rb") else f"{raw}.rb"
    if is_relative:
        p = (src_dir / base).resolve()
        if str(p) in all_paths:
            return str(p)
    else:
        p = (repo_root / "lib" / base).resolve()
        if str(p) in all_paths:
            return str(p)
    return None


def _resolve_relative_path(
    raw: str, src_dir: Path, repo_root: Path, all_paths: set[str],
) -> str | None:
    p = (src_dir / raw).resolve()
    if str(p) in all_paths:
        return str(p)
    return None


# ---------------------------------------------------------------------------
# FileAnalysis — result of analyzing one file
# ---------------------------------------------------------------------------

@dataclass
class FileAnalysis:
    # Repo-relative, like every path persisted to the graph: node identity has
    # to match across machines. Import resolution still runs on absolute paths
    # inside _analyze_file, which is the only place the filesystem is touched.
    path: str
    ext: str
    imported_paths: list[str] = field(default_factory=list)  # resolved, repo-relative
    chunk_calls: dict[str, list[str]] = field(default_factory=dict)  # chunk_id → callee names
    local_symbols: dict[str, list[str]] = field(default_factory=dict)  # terminal name → chunk_ids in THIS file


def _chunk_id(path: str, symbol: str) -> str:
    """Must match ingestion._chunk_id — *path* is repo-relative."""
    return hashlib.sha256(f"{path}::{symbol}".encode()).hexdigest()[:32]


def _rel(path: str, repo_root: str) -> str:
    """Absolute → repo-relative, forward slashes. Mirrors ingestion._rel_path."""
    try:
        rel = os.path.relpath(path, repo_root)
    except ValueError:
        return path
    return rel.replace(os.sep, "/")


# Reuse the same function-node types as ingestion.py (same parser, same AST)
_FUNCTION_TYPES = {
    # Python
    "function_definition", "async_function_definition",
    # JS/TS
    "function_declaration", "function_expression", "arrow_function",
    "method_definition",
    # Go
    "method_declaration", "function_literal",
    # Rust
    "function_item",
    # Java
    "method_declaration", "constructor_declaration",
    # C/C++ (same as Python: function_definition)
    # C#
    "method_declaration",
    # Ruby
    "method", "singleton_method",
    # PHP
    "method_declaration",
    # Kotlin
    "function_declaration",
    # Swift
    "function_declaration",
    # Scala
    "function_definition", "def_definition",
    # Bash
    "function_definition",
    # Lua
    "function_declaration", "local_function_statement",
    # Haskell
    "function",
    # Elixir
    "def", "defp",
}

_CLASS_TYPES = {
    "class_definition",      # Python / Scala
    "class_declaration",     # JS/TS / Java / C# / PHP / Kotlin / Swift
    "type_declaration",      # Go (struct-like)
    "impl_item",             # Rust (method block for a type)
    "class_specifier",       # C++
    "struct_specifier",      # C++
    "interface_declaration", # Java / C# / PHP / Kotlin / Swift
    # "module" excluded: root node type in Python's grammar (see ingestion.py note)
}


def _symbol_from_node(node: Node, parent_path: list[str], ext: str) -> str | None:
    """Extract dotted symbol name from a function/method node."""
    # Standard: look for 'name' field
    name_node = node.child_by_field_name("name")
    if name_node:
        name = name_node.text.decode("utf-8", errors="replace")
        return ".".join(parent_path + [name])

    # C/C++ function_definition: declarator → function_declarator → declarator (identifier)
    if ext in ("c", "h", "cpp", "cc", "cxx", "hpp", "hxx") and node.type == "function_definition":
        decl = node.child_by_field_name("declarator")
        if decl:
            fn_decl = None
            if decl.type == "function_declarator":
                fn_decl = decl
            else:
                for child in decl.children:
                    if child.type == "function_declarator":
                        fn_decl = child
                        break
            if fn_decl:
                inner = fn_decl.child_by_field_name("declarator")
                if inner and inner.type == "identifier":
                    return ".".join(parent_path + [inner.text.decode("utf-8", errors="replace")])

    return None


def _analyze_file(path: str, ext: str, code: bytes, repo_root: str, all_paths: set[str]) -> FileAnalysis:
    """Parse one file and return its calls + resolved imports (no DB access)."""
    rel = _rel(path, repo_root)
    parser = _get_parser(ext)
    if parser is None:
        return FileAnalysis(path=rel, ext=ext)

    tree = parser.parse(code)
    analysis = FileAnalysis(path=rel, ext=ext)
    module = Path(path).stem

    # Imports — resolved against the filesystem (absolute), stored relative.
    for spec in _extract_imports(tree.root_node, code, ext):
        resolved = _resolve_import(spec, path, ext, repo_root, all_paths)
        if resolved:
            analysis.imported_paths.append(_rel(resolved, repo_root))

    # CALLS — walk function nodes and collect calls made inside them
    def _walk(node: Node, parent_path: list[str]) -> None:
        if node.type in _FUNCTION_TYPES:
            symbol = _symbol_from_node(node, parent_path, ext)
            if symbol:
                cid = _chunk_id(rel, symbol)
                terminal = symbol.rsplit(".", 1)[-1]
                analysis.local_symbols.setdefault(terminal, []).append(cid)
                calls = _extract_calls(node, ext)
                if calls:
                    analysis.chunk_calls[cid] = calls
            return  # don't recurse into nested functions

        if node.type in _CLASS_TYPES:
            name_node = node.child_by_field_name("name")
            cls_name = name_node.text.decode("utf-8", errors="replace") if name_node else None
            new_path = parent_path + [cls_name] if cls_name else parent_path
            for child in node.children:
                _walk(child, new_path)
            return

        for child in node.children:
            _walk(child, parent_path)

    _walk(tree.root_node, [module])
    return analysis


# ---------------------------------------------------------------------------
# FalkorDB persistence
# ---------------------------------------------------------------------------

def _file_node_id(path: str) -> str:
    return hashlib.sha256(path.encode()).hexdigest()[:32]


def _upsert_file_nodes(g, group_id: str, entries: list[tuple[str, str]]) -> None:
    """Batch-upsert FileNodes. *entries* = list of (path, ext)."""
    if not entries:
        return
    now = int(time.time() * 1000)
    rows = [
        {"id": _file_node_id(p), "path": p, "ext": e}
        for p, e in dict.fromkeys(entries)  # dedupe, keep order
    ]
    for i in range(0, len(rows), _EDGE_BATCH):
        g.query(
            """
            UNWIND $files AS f
            MERGE (n:FileNode {id: f.id})
            SET n.group_id = $gid,
                n.path     = f.path,
                n.ext      = f.ext,
                n.updated_at = $now,
                n.created_at = COALESCE(n.created_at, $now)
            """,
            {"files": rows[i:i + _EDGE_BATCH], "gid": group_id, "now": now},
        )


def _write_imports(g, import_pairs: list[tuple[str, str]], built_at: int) -> None:
    """Batch-create IMPORTS edges stamped with the current run id.
    *import_pairs* = list of (source_path, target_path)."""
    if not import_pairs:
        return
    rows = [
        {"src": _file_node_id(s), "tgt": _file_node_id(t)}
        for s, t in dict.fromkeys(import_pairs)
    ]
    for i in range(0, len(rows), _EDGE_BATCH):
        g.query(
            """
            UNWIND $pairs AS p
            MATCH (s:FileNode {id: p.src})
            MATCH (t:FileNode {id: p.tgt})
            MERGE (s)-[r:IMPORTS]->(t)
            SET r.built_at = $built_at
            """,
            {"pairs": rows[i:i + _EDGE_BATCH], "built_at": built_at},
        )


# ---------------------------------------------------------------------------
# CALLS resolution — blocklist + hierarchical certainty
# ---------------------------------------------------------------------------

# Ultra-common method/function names (case-insensitive).  Linking on these
# by global name match produces mostly false positives, so they only ever
# resolve same-file.
_COMMON_NAMES = frozenset({
    # object protocol / stdlib-ish
    "tostring", "equals", "gethashcode", "gettype", "compareto", "hashcode",
    "clone", "copy", "deepcopy", "dispose", "finalize", "str", "repr", "hash",
    "iter", "len", "enter", "exit", "call", "new", "delete", "free",
    # lifecycle
    "main", "init", "initialize", "setup", "teardown", "configure", "create",
    "build", "make", "start", "stop", "restart", "reset", "run", "execute",
    "exec", "invoke", "apply", "begin", "end", "open", "close", "shutdown",
    # accessors / mutators
    "get", "set", "add", "remove", "insert", "push", "pop", "append",
    "extend", "update", "clear", "put", "fetch", "peek",
    # I/O & messaging
    "read", "write", "load", "save", "store", "send", "receive", "emit",
    "fire", "notify", "publish", "subscribe", "unsubscribe", "connect",
    "disconnect", "bind", "unbind", "register", "unregister", "flush",
    "sync", "wait", "sleep", "lock", "unlock", "acquire", "release",
    # transforms
    "parse", "format", "encode", "decode", "serialize", "deserialize",
    "tojson", "fromjson", "toarray", "tolist", "todict", "tostr",
    "convert", "transform", "replace", "split", "join", "trim", "strip",
    "tolower", "toupper", "substring", "slice", "concat",
    # validation / control
    "handle", "process", "check", "validate", "verify", "test", "match",
    "resolve", "reject", "then", "next", "prev", "first", "last", "accept",
    "visit", "dispatch", "filter", "map", "reduce", "sort", "compare",
    # queries
    "count", "size", "length", "contains", "exists", "find", "search",
    "index", "indexof", "keys", "values", "items", "name", "value", "type",
    "data", "result", "status", "info",
    # logging / UI
    "log", "print", "debug", "warn", "error", "trace", "render", "draw",
    "refresh", "show", "hide", "toggle", "focus",
})

_CAND_LIMIT = 16      # names with more global candidates than this are never linked
_MAX_PROBABLE = 5     # 2..5 candidates → probable edges; more → nothing
_NAME_BATCH = 5000    # names per resolution query
_EDGE_BATCH = 2000    # edges per UNWIND write
_FILE_BATCH = 500     # files analyzed per flush (bounds RAM on huge repos)


def _is_common_name(name: str) -> bool:
    return len(name) < 3 or name.lower() in _COMMON_NAMES


def _fetch_candidates(g, group_id: str, names: set[str], cache: dict) -> None:
    """Populate *cache* (name → list[{id, path}] | None) for unknown *names*.

    None means "too many candidates" (> _CAND_LIMIT), [] means no match.
    Two-phase: a cheap count query first, then candidates only for names
    with a bounded candidate set — keeps payloads small on huge repos.
    """
    # Matching is on the indexed term_name property (= last dotted segment of
    # symbol, written at ingestion + backfilled by ensure_schema).  This is
    # exactly equivalent to the old `symbol = name OR symbol ENDS WITH '.'+name`
    # (an undotted symbol's term_name IS the whole symbol) but index-served —
    # ENDS WITH forced a names × chunks cartesian scan that timed out on
    # kernel-sized repos.
    todo = [n for n in names if n not in cache]
    for i in range(0, len(todo), _NAME_BATCH):
        chunk = todo[i:i + _NAME_BATCH]
        res = g.query(
            """
            UNWIND $names AS name
            MATCH (c:CodeChunk {term_name: name})
            WHERE c.group_id = $gid AND c.valid = true
            RETURN name, count(c)
            """,
            {"names": chunk, "gid": group_id},
        )
        counts = {row[0]: int(row[1]) for row in res.result_set}
        shortlist = []
        for n in chunk:
            cnt = counts.get(n, 0)
            if cnt == 0:
                cache[n] = []
            elif cnt > _CAND_LIMIT:
                cache[n] = None
            else:
                shortlist.append(n)
        for j in range(0, len(shortlist), _NAME_BATCH):
            res2 = g.query(
                """
                UNWIND $names AS name
                MATCH (c:CodeChunk {term_name: name})
                WHERE c.group_id = $gid AND c.valid = true
                RETURN name, collect({id: c.id, path: c.path})
                """,
                {"names": shortlist[j:j + _NAME_BATCH], "gid": group_id},
            )
            for row in res2.result_set:
                cache[row[0]] = list(row[1])


def _write_call_edges(g, pairs: list[tuple[str, str]], certainty: str, built_at: int) -> int:
    """Batch-create CALLS edges with certainty + run-stamp properties.
    Returns edges created (re-derived existing edges are re-stamped, not counted)."""
    if not pairs:
        return 0
    rows = [{"src": s, "tgt": t} for s, t in dict.fromkeys(pairs)]
    created = 0
    for i in range(0, len(rows), _EDGE_BATCH):
        res = g.query(
            """
            UNWIND $pairs AS p
            MATCH (s:CodeChunk {id: p.src, valid: true})
            MATCH (t:CodeChunk {id: p.tgt})
            MERGE (s)-[r:CALLS]->(t)
            SET r.certainty = $certainty, r.built_at = $built_at
            """,
            {"pairs": rows[i:i + _EDGE_BATCH], "certainty": certainty, "built_at": built_at},
        )
        created += int(getattr(res, "relationships_created", 0) or 0)
    return created


def _resolve_and_write_calls(
    g, group_id: str, analyses: list[FileAnalysis], cache: dict, built_at: int,
) -> tuple[int, int]:
    """Resolve callee names for a batch of analyses and write CALLS edges.

    Hierarchical resolution:
      1. single candidate in the SAME file          → certain
      2. single candidate in a file IMPORTED by src → certain
      3. single candidate repo-wide (uncommon name) → certain
      4. 2..5 candidates repo-wide (uncommon name)  → probable (one edge each)
      5. >5 candidates, or common name unresolved locally → nothing

    Returns (certain_created, probable_created).
    """
    sites: list[tuple[str, str, FileAnalysis]] = []
    db_names: set[str] = set()
    for a in analyses:
        for src_cid, callees in a.chunk_calls.items():
            for name in dict.fromkeys(callees):
                sites.append((src_cid, name, a))
                # DB lookup only needed when same-file can't settle it alone
                if not _is_common_name(name) and len(a.local_symbols.get(name, [])) != 1:
                    db_names.add(name)

    if not sites:
        return 0, 0

    _fetch_candidates(g, group_id, db_names, cache)

    certain: list[tuple[str, str]] = []
    probable: list[tuple[str, str]] = []

    for src_cid, name, a in sites:
        # Tier 1 — same file (works even for common names)
        local = list(dict.fromkeys(a.local_symbols.get(name, [])))
        if local:
            if len(local) == 1 and local[0] != src_cid:
                certain.append((src_cid, local[0]))
            # multiple same-file candidates → ambiguous; recursion → no self edge
            continue

        # Tier 2+ requires an uncommon name
        if _is_common_name(name):
            continue

        cands = cache.get(name)
        if not cands:  # [] (no match) or None (too many)
            continue

        pool = [c for c in cands if c["id"] != src_cid]
        if not pool:
            continue

        # Tier 2 — unique candidate in a file imported by the source file
        imported_set = set(a.imported_paths)
        if imported_set:
            imported = [c for c in pool if c["path"] in imported_set]
            if len(imported) == 1:
                certain.append((src_cid, imported[0]["id"]))
                continue

        # Tier 3 — unique repo-wide
        if len(pool) == 1:
            certain.append((src_cid, pool[0]["id"]))
        # Tier 4 — small ambiguity → probable edges
        elif len(pool) <= _MAX_PROBABLE:
            for c in pool:
                probable.append((src_cid, c["id"]))
        # Tier 5 — too ambiguous → nothing

    # Write probable first so a pair that is also certain ends up "certain"
    n_probable = _write_call_edges(g, probable, "probable", built_at)
    n_certain = _write_call_edges(g, certain, "certain", built_at)
    return n_certain, n_probable


def _purge_stale_edges(g, group_id: str, run_id: int) -> tuple[int, int]:
    """Mark-and-sweep: delete CALLS / IMPORTS edges not re-stamped by *run_id*.

    Covers edges from removed source functions, edges from old resolvers
    (no built_at at all), and edges whose resolution no longer holds.
    Returns (calls_purged, imports_purged).
    """
    # Inline group_id → index-served node scan (group_id is indexed on both
    # CodeChunk and FileNode; verified with EXPLAIN against live FalkorDB).
    res = g.query(
        """
        MATCH (s:CodeChunk {group_id: $gid})-[r:CALLS]->()
        WHERE r.built_at IS NULL OR r.built_at < $run
        DELETE r
        """,
        {"gid": group_id, "run": run_id},
    )
    calls_purged = int(getattr(res, "relationships_deleted", 0) or 0)
    res = g.query(
        """
        MATCH (s:FileNode {group_id: $gid})-[r:IMPORTS]->()
        WHERE r.built_at IS NULL OR r.built_at < $run
        DELETE r
        """,
        {"gid": group_id, "run": run_id},
    )
    imports_purged = int(getattr(res, "relationships_deleted", 0) or 0)
    return calls_purged, imports_purged


def _purge_pre_migration_file_nodes(g, group_id: str) -> int:
    """Drop FileNodes keyed by an absolute path.

    Their id derives from the path, so the repo-relative keying created fresh
    nodes beside them; the old ones can never be re-derived and would keep
    surfacing machine-specific paths in imports_of / imported_by.
    """
    res = g.query(
        """
        MATCH (f:FileNode {group_id: $gid})
        WHERE f.path STARTS WITH '/'
        DETACH DELETE f
        """,
        {"gid": group_id},
    )
    return int(getattr(res, "nodes_deleted", 0) or 0)


def _purge_file_edges(g, source_path: str) -> None:
    """Remove all CALLS edges from chunks in *source_path* and IMPORTS from its FileNode.
    Called before re-analyzing a file.
    """
    # Remove CALLS edges from chunks in this file
    g.query(
        """
        MATCH (s:CodeChunk {path: $path})-[r:CALLS]->()
        DELETE r
        """,
        {"path": source_path},
    )
    # Remove IMPORTS edges from this file's FileNode
    fid = _file_node_id(source_path)
    g.query(
        "MATCH (f:FileNode {id: $id})-[r:IMPORTS]->() DELETE r",
        {"id": fid},
    )


# ---------------------------------------------------------------------------
# Supported extensions (union of ingestion + graph tiers)
# ---------------------------------------------------------------------------

_SUPPORTED_EXTS = frozenset({
    "py", "js", "jsx", "mjs", "cjs", "ts", "tsx", "mts",
    "go", "rs", "java", "c", "h", "cpp", "cc", "cxx", "hpp", "hxx",
    "cs", "rb", "php", "kt", "kts", "swift", "scala", "sc",
    "sh", "bash", "lua", "hs", "lhs", "ex", "exs",
})

_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "vendor", ".mypy_cache",
}

_MAX_FILE_BYTES = 512 * 1024


def _walk_repo(repo_path: str) -> Iterator[tuple[str, str]]:
    root = Path(repo_path)
    gitignore_file = root / ".gitignore"
    spec = pathspec.PathSpec.from_lines(
        "gitwildmatch",
        gitignore_file.read_text().splitlines() if gitignore_file.exists() else [],
    )
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(root)
        if spec.match_file(str(rel)):
            continue
        ext = p.suffix.lstrip(".")
        if ext not in _SUPPORTED_EXTS:
            continue
        if _get_parser(ext) is None:
            continue
        if p.stat().st_size > _MAX_FILE_BYTES:
            continue
        yield str(p), ext


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _flush_batch(
    g, group_id: str, batch: list[FileAnalysis], cache: dict, built_at: int,
) -> tuple[int, int, int]:
    """Persist one batch of analyses (FileNodes + IMPORTS + CALLS).
    Returns (imports_created, calls_certain, calls_probable)."""
    if not batch:
        return 0, 0, 0

    # FileNodes: sources + import targets, one UNWIND merge
    file_entries: list[tuple[str, str]] = []
    import_pairs: list[tuple[str, str]] = []
    for a in batch:
        file_entries.append((a.path, a.ext))
        for tp in a.imported_paths:
            file_entries.append((tp, Path(tp).suffix.lstrip(".")))
            import_pairs.append((a.path, tp))
    _upsert_file_nodes(g, group_id, file_entries)
    _write_imports(g, import_pairs, built_at)

    n_certain, n_probable = _resolve_and_write_calls(g, group_id, batch, cache, built_at)
    return len(import_pairs), n_certain, n_probable


def build_graph(group_id: str, repo_path: str) -> dict:
    """
    Build / refresh the full call graph for *repo_path*.
    Idempotent (MERGE semantics).  Called after bulk ingest (CodeChunks must
    already be in the DB).

    Single analysis pass, streamed in batches of _FILE_BATCH files so a
    kernel-sized repo never holds every FileAnalysis in RAM at once.

    Mark-and-sweep purge: every CALLS / IMPORTS edge written during this run
    is stamped with ``built_at = run_id``; once the full pass completes, any
    edge of the group whose built_at is missing or older is deleted (stale
    resolutions, removed source functions, pre-migration edges).
    Per-file failures (the ``errors`` counter) do NOT inhibit the purge —
    their edges are simply re-derived by the next successful run.  If the
    pass itself aborts (exception escaping this function), the purge never
    runs, so a partially-stamped graph is never swept.
    """
    from .db import get_graph

    g = get_graph(group_id)
    run_id = int(time.time() * 1000)

    # Collect all repo paths for import resolution (paths only — cheap)
    all_paths: set[str] = set()
    file_list: list[tuple[str, str]] = []
    for fpath, ext in _walk_repo(repo_path):
        all_paths.add(fpath)
        file_list.append((fpath, ext))

    total = imports_created = calls_certain = calls_probable = errors = 0
    cache: dict = {}  # callee name → candidates (shared across batches)
    batch: list[FileAnalysis] = []
    t0 = time.time()

    def _flush() -> None:
        nonlocal imports_created, calls_certain, calls_probable, batch
        imp, cert, prob = _flush_batch(g, group_id, batch, cache, run_id)
        imports_created += imp
        calls_certain += cert
        calls_probable += prob
        batch = []

    for idx, (fpath, ext) in enumerate(file_list, 1):
        try:
            code = Path(fpath).read_bytes()
            batch.append(_analyze_file(fpath, ext, code, repo_path, all_paths))
            total += 1
        except Exception as exc:
            log.warning("graph_builder: file error %s — %s", fpath, exc)
            errors += 1

        if len(batch) >= _FILE_BATCH:
            _flush()
        if idx % 1000 == 0:
            log.info(
                "build_graph progress — %d/%d files (%.0fs) imports=%d "
                "calls_certain=%d calls_probable=%d errors=%d",
                idx, len(file_list), time.time() - t0,
                imports_created, calls_certain, calls_probable, errors,
            )

    _flush()

    # Sweep: the full pass completed (per-file errors included) — remove
    # edges this run did not re-derive.
    calls_purged, imports_purged = _purge_stale_edges(g, group_id, run_id)
    files_purged = _purge_pre_migration_file_nodes(g, group_id)

    log.info(
        "build_graph done — files=%d imports=%d calls_certain=%d "
        "calls_probable=%d calls_purged=%d imports_purged=%d files_purged=%d "
        "errors=%d (%.0fs)",
        total, imports_created, calls_certain, calls_probable,
        calls_purged, imports_purged, files_purged, errors, time.time() - t0,
    )
    return {
        "files": total,
        "imports": imports_created,
        "calls_certain": calls_certain,
        "calls_probable": calls_probable,
        "calls_purged": calls_purged,
        "imports_purged": imports_purged,
        "files_purged": files_purged,
        "errors": errors,
    }


def rebuild_file_graph(group_id: str, file_path: str, repo_path: str) -> dict:
    """
    Incremental graph update for one file (PostToolUse / reindex_file).
    Purges old edges then re-derives with the same hierarchical resolution
    as build_graph.
    """
    from .db import get_graph

    g = get_graph(group_id)
    ext = Path(file_path).suffix.lstrip(".")
    if ext not in _SUPPORTED_EXTS or _get_parser(ext) is None:
        return {"skipped": True}

    rel = _rel(file_path, repo_path)

    try:
        code = Path(file_path).read_bytes()
    except FileNotFoundError:
        # File deleted — just purge its edges
        _purge_file_edges(g, rel)
        return {"deleted": True}

    _purge_file_edges(g, rel)

    # Collect repo paths for resolution (best-effort: use DB FileNodes).
    # FileNodes are stored repo-relative; import resolution walks the real
    # filesystem, so they have to be re-absolutised against the repo root.
    result = g.query(
        "MATCH (f:FileNode {group_id: $gid}) RETURN f.path",
        {"gid": group_id},
    )
    all_paths = {
        row[0] if os.path.isabs(row[0]) else str(Path(repo_path) / row[0])
        for row in result.result_set if row[0]
    }
    all_paths.add(file_path)

    analysis = _analyze_file(file_path, ext, code, repo_path, all_paths)

    # Stamp built_at for consistency with build_graph (a later full rebuild
    # re-derives these edges anyway and re-stamps them with its own run id).
    now = int(time.time() * 1000)

    _upsert_file_nodes(g, group_id, [(rel, ext)] + [
        (tp, Path(tp).suffix.lstrip(".")) for tp in analysis.imported_paths
    ])
    _write_imports(g, [(rel, tp) for tp in analysis.imported_paths], now)

    n_certain, n_probable = _resolve_and_write_calls(g, group_id, [analysis], {}, now)

    return {
        "imports": len(analysis.imported_paths),
        "call_sources": len(analysis.chunk_calls),
        "calls_certain": n_certain,
        "calls_probable": n_probable,
    }

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
# Call node specifications (certitude only — identifier targets only)
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
    "cs":    ("invocation_expression",   "expression", frozenset({"identifier"})),
    "rb":    ("call",                    "method",     frozenset({"identifier"})),
    "php":   ("function_call_expression","function",   frozenset({"name", "identifier"})),
    "kt":    ("call_expression",         None,         frozenset({"simple_identifier"})),
    "kts":   ("call_expression",         None,         frozenset({"simple_identifier"})),
    "swift": ("call_expression",         "function",   frozenset({"simple_identifier", "identifier"})),
    "lua":   ("function_call",           None,         frozenset({"identifier"})),
}


def _extract_calls(fn_node: Node, ext: str) -> list[str]:
    """Return callee names called within *fn_node* body (direct identifiers only)."""
    spec = _CALL_SPECS.get(ext)
    if not spec:
        return []
    call_type, name_field, id_types = spec

    results: list[str] = []

    def _walk(n: Node) -> None:
        if n.type == call_type:
            if name_field:
                target = n.child_by_field_name(name_field)
                if target and target.type in id_types:
                    name = target.text.decode("utf-8", errors="replace").strip()
                    if name:
                        results.append(name)
            else:
                # Find the first child whose type is an accepted identifier
                for child in n.children:
                    if child.type in id_types:
                        name = child.text.decode("utf-8", errors="replace").strip()
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
    path: str
    ext: str
    imported_paths: list[str] = field(default_factory=list)  # resolved absolute paths
    chunk_calls: dict[str, list[str]] = field(default_factory=dict)  # chunk_id → callee names


def _chunk_id(path: str, symbol: str) -> str:
    return hashlib.sha256(f"{path}::{symbol}".encode()).hexdigest()[:32]


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
    parser = _get_parser(ext)
    if parser is None:
        return FileAnalysis(path=path, ext=ext)

    tree = parser.parse(code)
    analysis = FileAnalysis(path=path, ext=ext)
    module = Path(path).stem

    # Imports
    for spec in _extract_imports(tree.root_node, code, ext):
        resolved = _resolve_import(spec, path, ext, repo_root, all_paths)
        if resolved:
            analysis.imported_paths.append(resolved)

    # CALLS — walk function nodes and collect calls made inside them
    def _walk(node: Node, parent_path: list[str]) -> None:
        if node.type in _FUNCTION_TYPES:
            symbol = _symbol_from_node(node, parent_path, ext)
            if symbol:
                cid = _chunk_id(path, symbol)
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


def _upsert_file_node(g, group_id: str, path: str, ext: str) -> None:
    fid = _file_node_id(path)
    now = int(time.time() * 1000)
    g.query(
        """
        MERGE (f:FileNode {id: $id})
        SET f.group_id = $gid,
            f.path     = $path,
            f.ext      = $ext,
            f.updated_at = $now,
            f.created_at = COALESCE(f.created_at, $now)
        """,
        {"id": fid, "gid": group_id, "path": path, "ext": ext, "now": now},
    )


def _write_imports(g, group_id: str, source_path: str, target_paths: list[str]) -> None:
    """Create IMPORTS edges between FileNodes."""
    if not target_paths:
        return
    src_id = _file_node_id(source_path)
    for tgt_path in target_paths:
        tgt_id = _file_node_id(tgt_path)
        g.query(
            """
            MATCH (s:FileNode {id: $src})
            MATCH (t:FileNode {id: $tgt})
            MERGE (s)-[:IMPORTS]->(t)
            """,
            {"src": src_id, "tgt": tgt_id},
        )


def _write_calls(g, group_id: str, chunk_calls: dict[str, list[str]]) -> None:
    """Resolve callee names → CodeChunk ids and create CALLS edges.
    Certitude policy: only create edge when exactly ONE CodeChunk in group_id
    has a symbol ending in .<callee_name> (or equals it).
    """
    if not chunk_calls:
        return

    for src_cid, callee_names in chunk_calls.items():
        # Verify source chunk exists AND is valid
        exists = g.query(
            "MATCH (c:CodeChunk {id: $id, valid: true}) RETURN c.id LIMIT 1",
            {"id": src_cid},
        )
        if not exists.result_set:
            continue

        for callee in callee_names:
            # Look for CodeChunks whose symbol ends with .callee or equals callee
            result = g.query(
                """
                MATCH (c:CodeChunk)
                WHERE c.group_id = $gid
                  AND c.valid = true
                  AND (c.symbol = $name OR c.symbol ENDS WITH $dotname)
                RETURN c.id
                LIMIT 2
                """,
                {"gid": group_id, "name": callee, "dotname": f".{callee}"},
            )
            rows = result.result_set
            if len(rows) == 1:
                tgt_cid = rows[0][0]
                if tgt_cid != src_cid:
                    g.query(
                        """
                        MATCH (s:CodeChunk {id: $src})
                        MATCH (t:CodeChunk {id: $tgt})
                        MERGE (s)-[:CALLS]->(t)
                        """,
                        {"src": src_cid, "tgt": tgt_cid},
                    )


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

def build_graph(group_id: str, repo_path: str) -> dict:
    """
    Build / refresh the full call graph for *repo_path*.
    Idempotent (MERGE semantics).  Called after bulk ingest.
    """
    from .db import get_graph

    g = get_graph(group_id)

    # Collect all repo paths for import resolution
    all_paths: set[str] = set()
    file_list: list[tuple[str, str]] = []
    for fpath, ext in _walk_repo(repo_path):
        all_paths.add(fpath)
        file_list.append((fpath, ext))

    total = 0
    imports_created = calls_created = errors = 0

    for fpath, ext in file_list:
        try:
            code = Path(fpath).read_bytes()
            analysis = _analyze_file(fpath, ext, code, repo_path, all_paths)

            # Upsert FileNode
            _upsert_file_node(g, group_id, fpath, ext)

            # IMPORTS edges
            if analysis.imported_paths:
                # Ensure target FileNodes exist first
                for tp in analysis.imported_paths:
                    _upsert_file_node(g, group_id, tp, Path(tp).suffix.lstrip("."))
                _write_imports(g, group_id, fpath, analysis.imported_paths)
                imports_created += len(analysis.imported_paths)

            total += 1
        except Exception as exc:
            log.warning("graph_builder: file error %s — %s", fpath, exc)
            errors += 1

    # CALLS edges — second pass (all chunks must be in DB first)
    for fpath, ext in file_list:
        try:
            code = Path(fpath).read_bytes()
            analysis = _analyze_file(fpath, ext, code, repo_path, all_paths)
            if analysis.chunk_calls:
                _write_calls(g, group_id, analysis.chunk_calls)
                calls_created += sum(len(v) for v in analysis.chunk_calls.values())
        except Exception as exc:
            log.warning("graph_builder: calls pass error %s — %s", fpath, exc)

    log.info(
        "build_graph done — files=%d imports=%d calls_candidates=%d errors=%d",
        total, imports_created, calls_created, errors,
    )
    return {"files": total, "imports": imports_created, "calls_candidates": calls_created, "errors": errors}


def rebuild_file_graph(group_id: str, file_path: str, repo_path: str) -> dict:
    """
    Incremental graph update for one file (PostToolUse / reindex_file).
    Purges old edges then re-derives.
    """
    from .db import get_graph

    g = get_graph(group_id)
    ext = Path(file_path).suffix.lstrip(".")
    if ext not in _SUPPORTED_EXTS or _get_parser(ext) is None:
        return {"skipped": True}

    try:
        code = Path(file_path).read_bytes()
    except FileNotFoundError:
        # File deleted — just purge its edges
        _purge_file_edges(g, file_path)
        return {"deleted": True}

    _purge_file_edges(g, file_path)

    # Collect repo paths for resolution (best-effort: use DB FileNodes)
    result = g.query(
        "MATCH (f:FileNode {group_id: $gid}) RETURN f.path",
        {"gid": group_id},
    )
    all_paths = {row[0] for row in result.result_set if row[0]}
    all_paths.add(file_path)

    analysis = _analyze_file(file_path, ext, code, repo_path, all_paths)

    _upsert_file_node(g, group_id, file_path, ext)

    if analysis.imported_paths:
        for tp in analysis.imported_paths:
            _upsert_file_node(g, group_id, tp, Path(tp).suffix.lstrip("."))
        _write_imports(g, group_id, file_path, analysis.imported_paths)

    if analysis.chunk_calls:
        _write_calls(g, group_id, analysis.chunk_calls)

    return {
        "imports": len(analysis.imported_paths),
        "call_sources": len(analysis.chunk_calls),
    }

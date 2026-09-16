"""Integration tests for the call graph builder (graph_builder.py).

Run inside the mcp container (tree-sitter parsers + live FalkorDB):
    docker exec -w .../market-mem/mcp market-mem-mcp-1 \
        python -m pytest tests/test_graph_builder.py -p no:cacheprovider -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import graph_builder as gb  # noqa: E402
from server.db import get_graph  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _analyze(tmp_path: Path, name: str, code: str) -> gb.FileAnalysis:
    p = tmp_path / name
    p.write_text(code)
    ext = p.suffix.lstrip(".")
    return gb._analyze_file(str(p), ext, code.encode(), str(tmp_path), {str(p)})


def _all_calls(analysis: gb.FileAnalysis) -> list[str]:
    out: list[str] = []
    for calls in analysis.chunk_calls.values():
        out.extend(calls)
    return out


def _add_chunk(g, gid: str, root, path: str, symbol: str) -> str:
    """Insert a CodeChunk the way ingestion would (same id scheme).

    Ingestion keys chunks by their repo-relative path, so *root* (the repo
    root the builder will be pointed at) is needed to derive it."""
    path = gb._rel(path, str(root))
    cid = gb._chunk_id(path, symbol)
    g.query(
        """
        MERGE (c:CodeChunk {id: $id})
        SET c.group_id = $gid, c.path = $path, c.symbol = $symbol,
            c.term_name = $term, c.valid = true
        """,
        {"id": cid, "gid": gid, "path": path, "symbol": symbol,
         "term": symbol.rsplit(".", 1)[-1]},
    )
    return cid


def _edges_from(g, src_cid: str) -> dict[str, str]:
    """Return {target_chunk_id: certainty} for CALLS edges out of src_cid."""
    res = g.query(
        "MATCH (s:CodeChunk {id: $id})-[r:CALLS]->(t) RETURN t.id, r.certainty",
        {"id": src_cid},
    )
    return {row[0]: row[1] for row in res.result_set}


# ---------------------------------------------------------------------------
# Extraction (no DB) — C# and Python member accesses
# ---------------------------------------------------------------------------

def test_csharp_extraction_bare_and_member(tmp_path):
    analysis = _analyze(tmp_path, "svc.cs", """
class Service {
    void Handle() {
        Compute();
        helper.Transform(1);
        this.repo.PersistRecord(x);
    }
}
""")
    calls = _all_calls(analysis)
    assert "Compute" in calls          # bare identifier
    assert "Transform" in calls        # obj.Method() member access
    assert "PersistRecord" in calls    # chained this.x.Method()


def test_python_extraction_attribute_call(tmp_path):
    analysis = _analyze(tmp_path, "mod.py", """
def caller():
    compute()
    self.transform_data()
    a.b.deep_method()
""")
    calls = _all_calls(analysis)
    assert "compute" in calls
    assert "transform_data" in calls
    assert "deep_method" in calls


def test_member_extraction_other_tier1_langs(tmp_path):
    # JS member_expression / property
    js = _analyze(tmp_path, "a.js", "function f() { obj.doWork(); }")
    assert "doWork" in _all_calls(js)
    # Go selector_expression / field
    go = _analyze(tmp_path, "a.go", "package m\nfunc f() { obj.DoWork() }")
    assert "DoWork" in _all_calls(go)
    # Rust field_expression / field
    rs = _analyze(tmp_path, "a.rs", "fn f() { obj.do_work(); }")
    assert "do_work" in _all_calls(rs)
    # C field_expression via ->
    c = _analyze(tmp_path, "a.c", "void f() { p->do_work(); }")
    assert "do_work" in _all_calls(c)


# ---------------------------------------------------------------------------
# Blocklist
# ---------------------------------------------------------------------------

def test_common_name_blocklist_contents():
    assert gb._is_common_name("ToString")
    assert gb._is_common_name("Replace")
    assert gb._is_common_name("init")
    assert gb._is_common_name("ok")          # < 3 chars
    assert not gb._is_common_name("PersistRecord")


def test_common_name_no_global_edge(gid, tmp_path):
    """A common name (Replace) defined once repo-wide must NOT create an
    edge from an unrelated member call — the Regex.Replace false positive."""
    g = get_graph(gid)
    definer = tmp_path / "regle.cs"
    definer.write_text(
        "class RegleSuivi { string Replace(string s) { return s; } }"
    )
    caller = tmp_path / "caller.cs"
    caller.write_text(
        "class Caller { void Go() { var x = Regex.Replace(input, pat, rep); } }"
    )
    _add_chunk(g, gid, tmp_path, str(definer), "regle.RegleSuivi.Replace")
    src = _add_chunk(g, gid, tmp_path, str(caller), "caller.Caller.Go")

    stats = gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {}
    assert stats["calls_certain"] == 0
    assert stats["calls_probable"] == 0


def test_common_name_resolves_same_file(gid, tmp_path):
    """Blocklisted names still resolve when the definition is in the SAME file."""
    g = get_graph(gid)
    f = tmp_path / "svc.py"
    f.write_text("""
def replace(s):
    return s

def caller():
    return replace("x")
""")
    tgt = _add_chunk(g, gid, tmp_path, str(f), "svc.replace")
    src = _add_chunk(g, gid, tmp_path, str(f), "svc.caller")

    gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {tgt: "certain"}


# ---------------------------------------------------------------------------
# Hierarchical resolution
# ---------------------------------------------------------------------------

def test_same_file_beats_global_ambiguity(gid, tmp_path):
    """helper() defined in the caller's file AND elsewhere → edge goes to
    the same-file definition only, certainty certain."""
    g = get_graph(gid)
    a = tmp_path / "a.py"
    a.write_text("""
def build_widget():
    return 1

def caller():
    return build_widget()
""")
    b = tmp_path / "b.py"
    b.write_text("""
def build_widget():
    return 2
""")
    tgt_local = _add_chunk(g, gid, tmp_path, str(a), "a.build_widget")
    src = _add_chunk(g, gid, tmp_path, str(a), "a.caller")
    _add_chunk(g, gid, tmp_path, str(b), "b.build_widget")

    gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {tgt_local: "certain"}


def test_imported_file_resolution(gid, tmp_path):
    """Name defined in two files; the caller imports one of them → unique
    candidate among imported files wins with certainty certain."""
    g = get_graph(gid)
    util = tmp_path / "util.py"
    util.write_text("def frobnicate_value(x):\n    return x\n")
    other = tmp_path / "other.py"
    other.write_text("def frobnicate_value(x):\n    return -x\n")
    caller = tmp_path / "caller.py"
    caller.write_text("""
import util

def go():
    return frobnicate_value(1)
""")
    tgt_util = _add_chunk(g, gid, tmp_path, str(util), "util.frobnicate_value")
    _add_chunk(g, gid, tmp_path, str(other), "other.frobnicate_value")
    src = _add_chunk(g, gid, tmp_path, str(caller), "caller.go")

    gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {tgt_util: "certain"}


def test_unique_global_resolution(gid, tmp_path):
    """Single repo-wide candidate, uncommon name → certain (legacy behavior)."""
    g = get_graph(gid)
    d = tmp_path / "lib.py"
    d.write_text("def compute_checksum(b):\n    return 0\n")
    caller = tmp_path / "main.py"
    caller.write_text("def entry():\n    return compute_checksum(b'')\n")
    tgt = _add_chunk(g, gid, tmp_path, str(d), "lib.compute_checksum")
    src = _add_chunk(g, gid, tmp_path, str(caller), "main.entry")

    stats = gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {tgt: "certain"}
    assert stats["calls_certain"] == 1


def test_probable_edges_for_small_ambiguity(gid, tmp_path):
    """2..5 repo-wide candidates, no local/import signal → probable edge
    to each candidate."""
    g = get_graph(gid)
    targets = []
    for i in range(3):
        f = tmp_path / f"impl{i}.py"
        f.write_text("def render_invoice(x):\n    return x\n")
        targets.append(_add_chunk(g, gid, tmp_path, str(f), f"impl{i}.render_invoice"))
    caller = tmp_path / "caller.py"
    caller.write_text("def go():\n    return render_invoice(1)\n")
    src = _add_chunk(g, gid, tmp_path, str(caller), "caller.go")

    stats = gb.build_graph(gid, str(tmp_path))
    edges = _edges_from(g, src)
    assert edges == {t: "probable" for t in targets}
    assert stats["calls_probable"] == 3


def test_too_many_candidates_no_edge(gid, tmp_path):
    """>5 repo-wide candidates → no edges at all."""
    g = get_graph(gid)
    for i in range(6):
        f = tmp_path / f"impl{i}.py"
        f.write_text("def render_invoice(x):\n    return x\n")
        _add_chunk(g, gid, tmp_path, str(f), f"impl{i}.render_invoice")
    caller = tmp_path / "caller.py"
    caller.write_text("def go():\n    return render_invoice(1)\n")
    src = _add_chunk(g, gid, tmp_path, str(caller), "caller.go")

    gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {}


def test_csharp_member_call_end_to_end(gid, tmp_path):
    """C# obj.Method() resolves to a unique repo-wide definition (the bug
    that produced 0 C# edges: wrong field + no member access support)."""
    g = get_graph(gid)
    svc = tmp_path / "svc.cs"
    svc.write_text("class Repo { void PersistRecord(int x) { } }")
    caller = tmp_path / "caller.cs"
    caller.write_text("class C { void Go() { repo.PersistRecord(1); LocalHelperFn(); } }")
    tgt = _add_chunk(g, gid, tmp_path, str(svc), "svc.Repo.PersistRecord")
    src = _add_chunk(g, gid, tmp_path, str(caller), "caller.C.Go")

    gb.build_graph(gid, str(tmp_path))
    edges = _edges_from(g, src)
    assert edges == {tgt: "certain"}


# ---------------------------------------------------------------------------
# Incremental rebuild compatibility
# ---------------------------------------------------------------------------

def test_rebuild_file_graph_uses_new_resolution(gid, tmp_path):
    g = get_graph(gid)
    d = tmp_path / "lib.py"
    d.write_text("def compute_checksum(b):\n    return 0\n")
    caller = tmp_path / "main.py"
    caller.write_text("def entry():\n    return compute_checksum(b'')\n")
    tgt = _add_chunk(g, gid, tmp_path, str(d), "lib.compute_checksum")
    src = _add_chunk(g, gid, tmp_path, str(caller), "main.entry")

    gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {tgt: "certain"}

    # Incremental rebuild of the caller file must recreate the same edge
    result = gb.rebuild_file_graph(gid, str(caller), str(tmp_path))
    assert result["calls_certain"] == 1
    assert _edges_from(g, src) == {tgt: "certain"}


def test_build_graph_stats_shape(gid, tmp_path):
    (tmp_path / "a.py").write_text("def solo_fn():\n    pass\n")
    stats = gb.build_graph(gid, str(tmp_path))
    assert set(stats) == {
        "files", "imports", "calls_certain", "calls_probable",
        "calls_purged", "imports_purged", "files_purged", "errors",
    }
    assert stats["files"] == 1
    assert stats["errors"] == 0


# ---------------------------------------------------------------------------
# Mark-and-sweep purge of stale edges
# ---------------------------------------------------------------------------

def test_purge_legacy_edge_without_built_at(gid, tmp_path):
    """An edge left by the old resolver (no built_at) is swept by a full
    rebuild, and the counter reports it."""
    g = get_graph(gid)
    a = tmp_path / "a.py"
    a.write_text("def standalone_fn():\n    pass\n")
    b = tmp_path / "b.py"
    b.write_text("def other_fn():\n    pass\n")
    ca = _add_chunk(g, gid, tmp_path, str(a), "a.standalone_fn")
    cb = _add_chunk(g, gid, tmp_path, str(b), "b.other_fn")
    # Legacy edge: no built_at, no certainty — not derivable from the code
    g.query(
        "MATCH (s:CodeChunk {id: $src}), (t:CodeChunk {id: $tgt}) "
        "CREATE (s)-[:CALLS]->(t)",
        {"src": ca, "tgt": cb},
    )

    stats = gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, ca) == {}
    assert stats["calls_purged"] == 1


def test_rederived_edge_survives_purge(gid, tmp_path):
    """An edge the run re-derives gets the run's built_at and survives;
    a second full rebuild purges nothing and keeps the same edge set."""
    g = get_graph(gid)
    d = tmp_path / "lib.py"
    d.write_text("def compute_checksum(b):\n    return 0\n")
    caller = tmp_path / "main.py"
    caller.write_text("def entry():\n    return compute_checksum(b'')\n")
    tgt = _add_chunk(g, gid, tmp_path, str(d), "lib.compute_checksum")
    src = _add_chunk(g, gid, tmp_path, str(caller), "main.entry")

    gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {tgt: "certain"}

    stats2 = gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {tgt: "certain"}
    assert stats2["calls_purged"] == 0
    total = g.query("MATCH ()-[r:CALLS]->() RETURN count(r)").result_set[0][0]
    assert total == 1  # no duplicates, no growth


def test_purge_edge_of_removed_source_function(gid, tmp_path):
    """When the calling function disappears from the file, its CALLS edge
    disappears after the next full rebuild."""
    g = get_graph(gid)
    d = tmp_path / "lib.py"
    d.write_text("def compute_checksum(b):\n    return 0\n")
    caller = tmp_path / "main.py"
    caller.write_text("def entry():\n    return compute_checksum(b'')\n")
    tgt = _add_chunk(g, gid, tmp_path, str(d), "lib.compute_checksum")
    src = _add_chunk(g, gid, tmp_path, str(caller), "main.entry")

    gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {tgt: "certain"}

    # The caller function is removed from the source (chunk may linger in
    # the DB until ingestion cleanup — the edge must still be swept)
    caller.write_text("VERSION = 1\n")
    stats = gb.build_graph(gid, str(tmp_path))
    assert _edges_from(g, src) == {}
    assert stats["calls_purged"] == 1


def test_rebuild_file_graph_stamps_built_at(gid, tmp_path):
    g = get_graph(gid)
    d = tmp_path / "lib.py"
    d.write_text("def compute_checksum(b):\n    return 0\n")
    caller = tmp_path / "main.py"
    caller.write_text("def entry():\n    return compute_checksum(b'')\n")
    _add_chunk(g, gid, tmp_path, str(d), "lib.compute_checksum")
    src = _add_chunk(g, gid, tmp_path, str(caller), "main.entry")
    # FileNodes must exist for rebuild's path collection
    gb.build_graph(gid, str(tmp_path))

    result = gb.rebuild_file_graph(gid, str(caller), str(tmp_path))
    assert result["calls_certain"] == 1
    res = g.query(
        "MATCH (s:CodeChunk {id: $id})-[r:CALLS]->() RETURN r.built_at",
        {"id": src},
    )
    assert res.result_set and res.result_set[0][0] is not None


def test_import_edge_purge(gid, tmp_path):
    """A stale IMPORTS edge (no built_at) between the group's FileNodes is
    swept and counted."""
    g = get_graph(gid)
    a = tmp_path / "a.py"
    a.write_text("X = 1\n")
    b = tmp_path / "b.py"
    b.write_text("Y = 2\n")
    # Pre-create FileNodes with a legacy IMPORTS edge (a does NOT import b)
    gb._upsert_file_nodes(g, gid, [(str(a), "py"), (str(b), "py")])
    g.query(
        "MATCH (s:FileNode {id: $src}), (t:FileNode {id: $tgt}) "
        "CREATE (s)-[:IMPORTS]->(t)",
        {"src": gb._file_node_id(str(a)), "tgt": gb._file_node_id(str(b))},
    )

    stats = gb.build_graph(gid, str(tmp_path))
    assert stats["imports_purged"] == 1
    total = g.query("MATCH ()-[r:IMPORTS]->() RETURN count(r)").result_set[0][0]
    assert total == 0

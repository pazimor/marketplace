"""
Scale benchmark — mapping quality without embeddings.

Ingests CodeChunk nodes for a repo WITHOUT computing embeddings (the vector
index tolerates a missing `emb` property), then runs the call-graph builder
and reports node/edge ratios.  Intended for very large repos (e.g. the Linux
kernel) where paying the embedding cost just to measure mapping quality would
be prohibitive.

Usage (inside the mcp container):
    python -m server.bench --repo /path/to/repo --group-id bench_xyz [--limit-files N]

Cleanup of the throwaway graph is the caller's responsibility:
    python -c "from server.db import get_graph; get_graph('bench_xyz').delete()"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from .db import get_graph
from .ingestion import (
    _content_hash,
    _chunk_id,
    _extract_chunks,
    _rel_path,
    iter_source_files,
)
from .schema import ensure_schema

_BATCH_SIZE = 500
_PROGRESS_EVERY = 200  # files


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


_UPSERT_BATCH_QUERY = """
UNWIND $rows AS r
MERGE (c:CodeChunk {id: r.id})
SET c.group_id     = $gid,
    c.path         = r.path,
    c.rel_path     = r.rel_path,
    c.symbol       = r.symbol,
    c.term_name    = r.term,
    c.kind         = r.kind,
    c.lang         = r.lang,
    c.signature    = r.sig,
    c.start_line   = r.sl,
    c.end_line     = r.el,
    c.start_byte   = r.sb,
    c.end_byte     = r.eb,
    c.content_hash = r.chash,
    c.loc          = r.el - r.sl + 1,
    c.updated_at   = $now,
    c.indexed_at   = $now,
    c.valid        = true,
    c.created_at   = COALESCE(c.created_at, $now)
"""


def _flush_batch(g, group_id: str, rows: list[dict]) -> None:
    if not rows:
        return
    g.query(_UPSERT_BATCH_QUERY, {"rows": rows, "gid": group_id, "now": int(time.time() * 1000)})


def run_bench(repo_path: str, group_id: str, limit_files: int | None = None) -> dict:
    g = get_graph(group_id)
    ensure_schema(group_id)

    report: dict = {"repo": repo_path, "group_id": group_id}
    counters: dict[str, int] = {}

    # ---- Phase 1: walk + chunk + batch insert (no embeddings) -------------
    t0 = time.monotonic()
    files = chunks_total = read_errors = 0
    batch: list[dict] = []
    # kept in memory for the local unresolved-callee analysis (phase 4)
    all_symbols: list[str] = []
    ingested_files: list[tuple[str, str]] = []

    for file_path, ext, code in iter_source_files(repo_path, counters):
        if limit_files is not None and files >= limit_files:
            break
        files += 1
        ingested_files.append((file_path, ext))
        try:
            chunks = _extract_chunks(code, file_path, ext)
        except Exception as exc:
            _log(f"[bench] parse error {file_path}: {exc}")
            read_errors += 1
            continue
        rel = _rel_path(file_path, repo_path)
        for ch in chunks:
            chunks_total += 1
            all_symbols.append(ch.symbol)
            batch.append({
                "id": _chunk_id(ch.path, ch.symbol),
                "path": ch.path,
                "rel_path": rel,
                "symbol": ch.symbol,
                "term": ch.symbol.rsplit(".", 1)[-1],
                "kind": ch.kind,
                "lang": ch.lang,
                "sig": ch.signature,
                "sl": ch.start_line,
                "el": ch.end_line,
                "sb": ch.start_byte,
                "eb": ch.end_byte,
                "chash": _content_hash(ch.content),
            })
            if len(batch) >= _BATCH_SIZE:
                _flush_batch(g, group_id, batch)
                batch = []
        if files % _PROGRESS_EVERY == 0:
            _log(f"[bench] ingest: {files} files, {chunks_total} chunks…")
    _flush_batch(g, group_id, batch)
    t_ingest = time.monotonic() - t0
    _log(f"[bench] ingest done: {files} files, {chunks_total} chunks in {t_ingest:.1f}s")

    report["files"] = files
    report["chunks"] = chunks_total
    report["read_errors"] = read_errors
    report["skipped"] = {k: counters.get(k, 0) for k in
                        ("skipped_vendor", "skipped_minified", "skipped_generated")}

    # ---- Phase 2: call graph ---------------------------------------------
    from .graph_builder import build_graph

    t0 = time.monotonic()
    graph_stats = build_graph(group_id, repo_path)
    t_graph = time.monotonic() - t0
    _log(f"[bench] build_graph done in {t_graph:.1f}s — {graph_stats}")
    report["build_graph"] = graph_stats

    # ---- Phase 3: edge counts from the DB --------------------------------
    t0 = time.monotonic()
    calls_total = g.query("MATCH ()-[r:CALLS]->() RETURN count(r)").result_set[0][0]
    imports_total = g.query("MATCH ()-[r:IMPORTS]->() RETURN count(r)").result_set[0][0]
    # by certainty, when the property exists on edges
    by_certainty: dict[str, int] = {}
    try:
        res = g.query(
            "MATCH ()-[r:CALLS]->() WHERE r.certainty IS NOT NULL "
            "RETURN r.certainty, count(r)"
        )
        for cert, n in res.result_set:
            by_certainty[str(cert)] = n
    except Exception:
        pass

    report["edges"] = {
        "calls": calls_total,
        "calls_by_certainty": by_certainty or None,
        "imports": imports_total,
    }
    report["ratios"] = {
        "chunks_per_file": round(chunks_total / files, 2) if files else 0,
        "calls_per_chunk": round(calls_total / chunks_total, 3) if chunks_total else 0,
        "imports_per_file": round(imports_total / files, 3) if files else 0,
    }

    # ---- Phase 4: unresolved callee names (in-memory replica of the
    #      graph_builder certitude policy: exactly one symbol matching
    #      `name` or `*.name` resolves; 0 or >=2 does not) ------------------
    from .graph_builder import _analyze_file as _gb_analyze

    last_seg: Counter = Counter()
    exact: Counter = Counter()
    for sym in all_symbols:
        exact[sym] += 1
        last_seg[sym.rsplit(".", 1)[-1]] += 1

    callee_freq: Counter = Counter()
    analyzed = 0
    all_paths = {fp for fp, _ in ingested_files}
    for file_path, ext in ingested_files:
        try:
            code = Path(file_path).read_bytes()
            analysis = _gb_analyze(file_path, ext, code, repo_path, all_paths)
            for names in analysis.chunk_calls.values():
                callee_freq.update(names)
            analyzed += 1
            if analyzed % _PROGRESS_EVERY == 0:
                _log(f"[bench] callee analysis: {analyzed} files…")
        except Exception as exc:
            _log(f"[bench] analysis error {file_path}: {exc}")

    def _match_count(name: str) -> int:
        """In-memory replica of graph_builder._write_calls resolution:
        symbols where s == name OR s ENDS WITH ".name"."""
        if "." not in name:
            # every symbol whose last dotted segment == name matches
            # (bare-equal symbols are included in last_seg too)
            return last_seg.get(name, 0)
        dot = f".{name}"
        return exact.get(name, 0) + sum(
            v for s, v in exact.items() if s.endswith(dot)
        )

    unresolved_total = 0
    top_unresolved: list[tuple[str, int]] = []
    for name, freq in callee_freq.most_common():
        if _match_count(name) != 1:
            unresolved_total += 1
            if len(top_unresolved) < 10:
                top_unresolved.append((name, freq))
    report["callees"] = {
        "unique_names": len(callee_freq),
        "total_call_sites": sum(callee_freq.values()),
        "unresolved_unique_names": unresolved_total,
        "top_unresolved": [{"name": n, "count": c} for n, c in top_unresolved],
    }
    t_analysis = time.monotonic() - t0

    report["durations_s"] = {
        "ingest": round(t_ingest, 2),
        "build_graph": round(t_graph, 2),
        "edge_counts_and_analysis": round(t_analysis, 2),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m server.bench",
        description="Mapping-quality benchmark without embeddings.",
    )
    ap.add_argument("--repo", required=True, help="Path to the repo to benchmark")
    ap.add_argument("--group-id", required=True,
                    help="Throwaway group_id (use a bench_ prefix)")
    ap.add_argument("--limit-files", type=int, default=None,
                    help="Stop after N files (smoke runs)")
    args = ap.parse_args(argv)

    if not args.group_id.startswith("bench_"):
        _log("[bench] warning: group-id does not start with 'bench_' — "
             "make sure this is not a real project graph")

    report = run_bench(args.repo, args.group_id, args.limit_files)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

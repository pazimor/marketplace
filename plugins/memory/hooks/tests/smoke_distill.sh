#!/bin/sh
# Real-token smoke test for the distiller — run MANUALLY, costs ~1 haiku call
# + 1 sonnet call on a 4-turn transcript. Requires: Docker stack up, `claude`
# CLI logged in. Run from the repo root:
#
#   sh plugins/memory/hooks/tests/smoke_distill.sh
#
# It fabricates one tiny fake past-session transcript in a temp dir and runs
# the distiller synchronously against the real MCP server. Check the result:
# the ledger entry and (probably) one memory about "commit messages in French".
set -eu

REPO="$(pwd)"
TDIR="$(mktemp -d)"
SID="smoke-$(date +%s)"

python3 - "$TDIR/$SID.jsonl" <<'EOF'
import json, sys
turns = [
    ("user", "from now on, always write commit messages in French for this project"),
    ("assistant", "Understood — commit messages will be written in French from now on."),
    ("user", "also I found why CI was red: the lockfile was regenerated with npm 11, pinning npm 10 fixed it"),
    ("assistant", "Good catch: root cause recorded — lockfile drift between npm 10 and 11."),
]
lines = [json.dumps({"message": {"role": r, "content": c}}) for r, c in turns]
lines += [json.dumps({"type": "system", "content": "x" * 200})] * 20  # size gate
open(sys.argv[1], "w").write("\n".join(lines))
EOF

echo "--- distilling $SID (sync, real tokens) ---"
python3 "$(dirname "$0")/../_distill.py" \
    --repo "$REPO" --transcript-dir "$TDIR" --exclude-session none

GID=$(python3 -c "
import sys; sys.path.insert(0, 'plugins/memory/hooks')
from _lib import group_id; print(group_id('$REPO'))")

echo "--- ledger ---"
curl -sk "https://127.0.0.1:7333/sessions/$GID" | python3 -m json.tool | head -20
rm -rf "$TDIR"

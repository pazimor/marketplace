#!/usr/bin/env python3
"""Validator for the files of the orchestration plugin (python3 stdlib only).

Checks, under a project root:
  - the manifests `.claude-plugin/marketplace.json` and `plugins/*/.claude-plugin/plugin.json`;
  - the frontmatter of agents (`plugins/*/agents/*.md`) and skills (`plugins/*/skills/*/SKILL.md`);
  - the canon grammar (`.claude/canon/*.md`);
  - the roadmap grammar (`.claude/roadmap.md`).

Each missing part is skipped: the script runs as well on this marketplace as on a project that only
uses the plugin (canon + roadmap only).

The grammar checked here is described in `docs/grammar.md`, which itself points to the SKILL.md files
(`canon-tracker`, `roadmap-tracker`), the only owners of the grammar (CANON:2).

Usage: python3 scripts/validate.py [ROOT] [--strict]
Exit code: 0 = no error, 1 = error(s) (or warning(s) with --strict), 2 = usage.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ERROR = "ERROR"
WARNING = "WARN"


@dataclass
class Finding:
    level: str
    code: str
    path: str
    line: int | None
    message: str

    def __str__(self) -> str:
        loc = self.path if self.line is None else f"{self.path}:{self.line}"
        return f"{self.level} {loc}: [{self.code}] {self.message}"


@dataclass
class Report:
    root: Path
    findings: list[Finding] = field(default_factory=list)

    def _add(self, level, code, path, line, message):
        try:
            rel = str(Path(path).resolve().relative_to(self.root.resolve()))
        except ValueError:
            rel = str(path)
        self.findings.append(Finding(level, code, rel, line, message))

    def error(self, code, path, line, message):
        self._add(ERROR, code, path, line, message)

    def warn(self, code, path, line, message):
        self._add(WARNING, code, path, line, message)

    @property
    def errors(self):
        return [f for f in self.findings if f.level == ERROR]

    @property
    def warnings(self):
        return [f for f in self.findings if f.level == WARNING]

    def codes(self, level=None):
        return [f.code for f in self.findings if level is None or f.level == level]


# ---------------------------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------------------------

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
DATE = r"\d{4}-\d{2}-\d{2}"


def valid_date(s: str) -> bool:
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def read_text(report: Report, path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.error("io.unreadable", path, None, f"cannot read: {exc}")
        return None


def load_json(report: Report, path: Path):
    # CANON:3 — same check as `python3 -c "import json; json.load(open(p))"`.
    text = read_text(report, path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        report.error("manifest.json", path, exc.lineno, f"invalid JSON: {exc.msg}")
        return None


# ---------------------------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------------------------


def check_manifests(report: Report, root: Path) -> None:
    plugin_manifests = sorted(root.glob("plugins/*/.claude-plugin/plugin.json"))
    plugins_by_dir: dict[Path, dict] = {}
    for path in plugin_manifests:
        data = load_json(report, path)
        if data is None:
            continue
        if not isinstance(data, dict):
            report.error("manifest.plugin", path, None, "the root must be a JSON object")
            continue
        plugins_by_dir[path.parent.parent.resolve()] = data
        name = data.get("name")
        if not isinstance(name, str) or not name:
            report.error("manifest.plugin-name", path, None, "`name` field required (non-empty string)")
        version = data.get("version")
        if version is None:
            report.error("manifest.plugin-version", path, None, "`version` field required (semver)")
        elif not isinstance(version, str) or not SEMVER_RE.match(version):
            report.error("manifest.plugin-version", path, None, f"`version` is not semver: {version!r}")

    mp_path = root / ".claude-plugin" / "marketplace.json"
    if not mp_path.is_file():
        return
    data = load_json(report, mp_path)
    if data is None:
        return
    if not isinstance(data, dict):
        report.error("manifest.marketplace", mp_path, None, "the root must be a JSON object")
        return
    if not isinstance(data.get("name"), str) or not data.get("name"):
        report.error("manifest.marketplace-name", mp_path, None, "`name` field required")
    owner = data.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("name"), str) or not owner.get("name"):
        report.error("manifest.marketplace-owner", mp_path, None, "`owner.name` field required")
    version = data.get("version")
    if version is not None and (not isinstance(version, str) or not SEMVER_RE.match(version)):
        report.error("manifest.marketplace-version", mp_path, None, f"`version` is not semver: {version!r}")
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        report.error("manifest.marketplace-plugins", mp_path, None, "`plugins` field required (list)")
        return

    seen_names: set[str] = set()
    listed_dirs: set[Path] = set()
    for i, entry in enumerate(plugins):
        where = f"plugins[{i}]"
        if not isinstance(entry, dict):
            report.error("manifest.marketplace-entry", mp_path, None, f"{where} must be an object")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            report.error("manifest.marketplace-entry", mp_path, None, f"{where}.name required")
            continue
        if name in seen_names:
            report.error("manifest.marketplace-duplicate", mp_path, None, f"plugin `{name}` listed twice")
        seen_names.add(name)
        source = entry.get("source")
        if source is None:
            report.error("manifest.marketplace-entry", mp_path, None, f"{where}.source required")
            continue
        if not isinstance(source, str):
            continue  # remote source (github/url object…): outside the repo, nothing to compare
        if not source.startswith("./"):
            report.error("manifest.marketplace-source", mp_path, None,
                         f"{where}.source (relative) must start with `./`: {source!r}")
            continue
        plugin_dir = (root / source).resolve()
        listed_dirs.add(plugin_dir)
        manifest = plugin_dir / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            report.error("manifest.marketplace-source", mp_path, None,
                         f"{where}.source `{source}` does not contain `.claude-plugin/plugin.json`")
            continue
        pdata = plugins_by_dir.get(plugin_dir)
        if pdata is None:
            pdata = load_json(report, manifest)
        if isinstance(pdata, dict) and pdata.get("name") != name:
            report.error("manifest.name-mismatch", mp_path, None,
                         f"{where}.name `{name}` ≠ `name` of {source}/.claude-plugin/plugin.json "
                         f"(`{pdata.get('name')}`)")
        if isinstance(pdata, dict) and "version" in entry and entry["version"] != pdata.get("version"):
            report.error("manifest.version-mismatch", mp_path, None,
                         f"{where}.version `{entry['version']}` ≠ version of plugin.json "
                         f"(`{pdata.get('version')}`)")

    for plugin_dir in plugins_by_dir:
        if plugin_dir not in listed_dirs:
            report.warn("manifest.unlisted-plugin", plugin_dir / ".claude-plugin" / "plugin.json", None,
                        "plugin missing from the catalog `.claude-plugin/marketplace.json`")


# ---------------------------------------------------------------------------------------------
# Frontmatter agents / skills
# ---------------------------------------------------------------------------------------------

MODEL_ALIASES = {"opus", "sonnet", "haiku", "fable", "inherit"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
# Model names appear only on the `model:` line of an agent's frontmatter (`CANON:22`).
MODEL_NAME_RE = re.compile(r"\b(opus|sonnet|haiku|fable)\b", re.IGNORECASE)
PLUGIN_AGENT_IGNORED = ("hooks", "mcpServers", "permissionMode")
# Mascots of the agents-info band (`MASCOTS` in plugins/agents-info/hooks/recap.ts); Claude Code ignores the field.
MASCOTS = {"scribe", "chef", "artist", "inspector", "courier", "artisan", "scholar", "mage", "bare"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FM_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:(?:\s+(.*?))?\s*$")


def _scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    # End-of-line comment on a bare scalar.
    return re.sub(r"\s+#.*$", "", raw)


def parse_frontmatter(text: str):
    """Minimal YAML parser for frontmatter: top-level keys, scalars, `|`/`>` blocks.

    Returns (dict key -> (value, line), end line) or (None, error message).
    Nested values (lists, maps) are returned as raw text.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "frontmatter missing (the file must start with `---`)"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, "frontmatter not closed (closing `---` missing)"
    data: dict[str, tuple[str, int]] = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":
            return None, f"line {i + 1}: unexpected indentation outside a value"
        m = FM_KEY_RE.match(line)
        if not m:
            return None, f"line {i + 1}: `key: value` expected"
        key, raw = m.group(1), (m.group(2) or "")
        start = i + 1
        i += 1
        block: list[str] = []
        while i < end and (not lines[i].strip() or lines[i][0] in " \t"):
            block.append(lines[i].strip())
            i += 1
        if raw[:1] in ("|", ">"):
            sep = "\n" if raw[0] == "|" else " "
            value = sep.join(b for b in block if b).strip()
        elif raw:
            value = _scalar(raw) if not block else " ".join([raw] + [b for b in block if b])
        else:
            value = "\n".join(b for b in block if b)
        if key in data:
            return None, f"line {start}: duplicate key `{key}`"
        data[key] = (value, start)
    return data, end


def check_frontmatter_file(report: Report, path: Path, kind: str) -> None:
    text = read_text(report, path)
    if text is None:
        return
    data, info = parse_frontmatter(text)
    if data is None:
        report.error("frontmatter.syntax", path, None, info)
        return
    for key in ("name", "description"):
        if key not in data or not data[key][0].strip():
            report.error(f"frontmatter.{key}", path, None, f"`{key}` field required")
    if "name" in data:
        name, line = data["name"]
        if name and not NAME_RE.match(name):
            report.warn("frontmatter.name-format", path, line,
                        f"`name` should use lowercase letters, digits and hyphens: {name!r}")
        if kind == "skill" and name and name != path.parent.name:
            report.warn("frontmatter.name-dir", path, line,
                        f"`name` ({name}) ≠ skill folder name ({path.parent.name})")
    if "model" in data:
        model, line = data["model"]
        if model not in MODEL_ALIASES and not re.match(r"^claude-[a-z0-9][a-z0-9.\-\[\]]*$", model):
            report.error("frontmatter.model", path, line,
                         f"invalid `model`: {model!r} (expected {sorted(MODEL_ALIASES)} or a `claude-*` ID)")
    if "effort" in data:
        effort, line = data["effort"]
        if effort not in EFFORTS:
            report.error("frontmatter.effort", path, line,
                         f"invalid `effort`: {effort!r} (expected {sorted(EFFORTS)})")
    if kind == "agent" and "mascot" in data:
        mascot, line = data["mascot"]
        if mascot not in MASCOTS:
            report.warn("frontmatter.mascot", path, line,
                        f"unknown `mascot`: {mascot!r} (expected {sorted(MASCOTS)}) — the band will use the model's trade instead")
    if kind == "agent":
        for key in PLUGIN_AGENT_IGNORED:
            if key in data:
                report.warn("frontmatter.plugin-agent-ignored", path, data[key][1],
                            f"`{key}` is ignored by Claude Code for an agent shipped by a plugin")


def check_frontmatters(report: Report, root: Path) -> None:
    for path in sorted(root.glob("plugins/*/agents/*.md")):
        check_frontmatter_file(report, path, "agent")
    for path in sorted(root.glob("plugins/*/skills/*/SKILL.md")):
        check_frontmatter_file(report, path, "skill")


def check_model_mentions(report: Report, root: Path) -> None:
    """No model name in a plugin outside the `model:` line of an agent's frontmatter."""
    for path in sorted(root.glob("plugins/**/*")):
        if not path.is_file() or path.suffix not in (".md", ".json"):
            continue
        text = read_text(report, path)
        if text is None:
            continue
        is_agent = path.parent.name == "agents" and path.suffix == ".md"
        for n, line in enumerate(text.splitlines(), 1):
            if is_agent and re.match(r"^model\s*:", line):
                continue
            m = MODEL_NAME_RE.search(line)
            if m:
                report.error("plugin.model-mention", path, n,
                             f"model name outside an agent's frontmatter: {m.group(0)!r} (`CANON:22`)")


# ---------------------------------------------------------------------------------------------
# Canon — grammar: canon-tracker skill, § "Entry grammar"
# ---------------------------------------------------------------------------------------------

CANON_HEAD = (
    r"`CANON:(?P<id>\d+)` \[(?:USER:(?P<user>\S(?:[^\]]*?\S)?)|(?P<model>MODEL)) (?P<date>" + DATE + r")\]"
)
CANON_LIVE_RE = re.compile(r"^" + CANON_HEAD + r" (?P<text>\S.*)$")
CANON_HEAD_RE = re.compile(r"^" + CANON_HEAD + r"(?P<rest>.*)$")
OBSOLETE_RE = re.compile(r"—\s*obsolete\s+(?P<date>" + DATE + r")\s*:\s*(?P<reason>\S.*)$")
PROMOTED = "(promoted from MODEL)"
CANON_REF_RE = re.compile(r"\bCANON:(\d+)\b")


@dataclass
class CanonEntry:
    id: int
    path: Path
    line: int
    deprecated: bool
    text: str


def _blocks(lines: list[str]):
    """Splits into top-level list blocks: (line, joined text), plus the stray prose."""
    blocks: list[tuple[int, list[str]]] = []
    stray: list[tuple[int, str]] = []
    headings: list[tuple[int, str]] = []
    current = None
    for n, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if not line.strip():
            current = None
            continue
        if line.startswith("#"):
            headings.append((n, line))
            current = None
        elif line.startswith("- "):
            current = (n, [line[2:].strip()])
            blocks.append(current)
        elif line[0] in " \t" and current is not None:
            current[1].append(line.strip())
        else:
            stray.append((n, line))
            current = None
    return [(n, " ".join(parts)) for n, parts in blocks], stray, headings


def parse_canon_entry(report: Report, path: Path, line: int, text: str) -> CanonEntry | None:
    struck_whole = text.startswith("~~")
    if struck_whole:
        close = text.find("~~", 2)
        if close == -1:
            report.error("canon.strike", path, line, "opening `~~` without a closing `~~`")
            return None
        inner, after = text[2:close], text[close + 2:]
        m = CANON_LIVE_RE.match(inner)
        if not m:
            report.error("canon.entry", path, line,
                         "struck entry malformed: expected ~~`CANON:n` [USER:<name> YYYY-MM-DD|MODEL YYYY-MM-DD] <point>~~")
            return None
        body, deprecated = m.group("text"), True
    else:
        m = CANON_HEAD_RE.match(text)
        if not m:
            report.error("canon.entry", path, line,
                         "malformed entry: expected `CANON:n` [USER:<name> YYYY-MM-DD] <point> "
                         "or `CANON:n` [MODEL YYYY-MM-DD] <point>")
            return None
        rest = m.group("rest")
        if not rest.startswith(" ") or not rest.strip():
            report.error("canon.entry", path, line, "the entry's point is empty")
            return None
        body = rest.strip()
        deprecated = body.startswith("~~")
        after = ""
        if deprecated:
            # Second reading of "strike through": only the point is struck, the header stays.
            close = body.find("~~", 2)
            if close == -1:
                report.error("canon.strike", path, line, "opening `~~` without a closing `~~`")
                return None
            body, after = body[2:close], body[close + 2:]
            if not body.strip():
                report.error("canon.entry", path, line, "the struck point is empty")
                return None

    cid = int(m.group("id"))
    date = m.group("date")
    if not valid_date(date):
        report.error("canon.date", path, line, f"invalid date: {date}")

    obsolete = OBSOLETE_RE.search(after if deprecated else body)
    if deprecated:
        if not obsolete:
            report.error("canon.obsolete-missing", path, line,
                         "struck entry without `— obsolete YYYY-MM-DD: <reason>` (at end of line or below)")
        else:
            odate = obsolete.group("date")
            if not valid_date(odate):
                report.error("canon.date", path, line, f"invalid obsolete date: {odate}")
            elif valid_date(date) and odate < date:
                report.warn("canon.obsolete-before-entry", path, line,
                            f"obsolete on {odate}, before the entry date ({date})")
        stray_after = OBSOLETE_RE.sub("", after).strip() if obsolete else after.strip()
        if stray_after:
            report.error("canon.entry", path, line, f"text outside the grammar after the struck entry: {stray_after!r}")
    elif obsolete:
        report.error("canon.obsolete-unstruck", path, line,
                     "`— obsolete …` mark on an entry that is not struck (strike the text with `~~…~~`)")
    elif "~~" in body:
        report.error("canon.strike", path, line, "`~~` in the middle of an entry: strike the whole point")

    if body.rstrip().endswith(PROMOTED) and m.group("model"):
        report.error("canon.promotion", path, line, f"`{PROMOTED}` on a [MODEL] entry")
    return CanonEntry(cid, path, line, deprecated, text)


def check_canon(report: Report, root: Path) -> dict[int, CanonEntry]:
    canon_dir = root / ".claude" / "canon"
    entries: dict[int, CanonEntry] = {}
    if not canon_dir.is_dir():
        return entries
    files = sorted(canon_dir.glob("*.md"))
    for path in files:
        if path.name == "misc.md":
            report.error("canon.misc", path, None,
                         "never `misc.md`: an entry that fits nowhere signals a theme to name")
        text = read_text(report, path)
        if text is None:
            continue
        lines = text.splitlines()
        blocks, stray, headings = _blocks(lines)
        first = next(((n, l) for n, l in enumerate(lines, 1) if l.strip()), None)
        if first is None or not re.match(r"^# \S", first[1]):
            report.error("canon.title", path, first[0] if first else None,
                         "the file must start with a title `# <Theme>`")
        for n, line in stray:
            report.error("canon.prose", path, n, f"prose outside an entry: {line.strip()[:60]!r}")
        for n, text in blocks:
            entry = parse_canon_entry(report, path, n, text)
            if entry is None:
                continue
            if entry.id in entries:
                prev = entries[entry.id]
                rel = prev.path.name
                report.error("canon.duplicate-id", path, n,
                             f"`CANON:{entry.id}` already used ({rel}:{prev.line}) — IDs must be unique across the folder")
            else:
                entries[entry.id] = entry
    # Cross-references: a cited `CANON:n` must exist.
    for entry in entries.values():
        for ref in CANON_REF_RE.findall(entry.text):
            if int(ref) not in entries:
                report.warn("canon.unknown-ref", entry.path, entry.line, f"reference to unknown `CANON:{ref}`")
    return entries


# ---------------------------------------------------------------------------------------------
# Roadmap — grammar: roadmap-tracker skill, § "File grammar"
# ---------------------------------------------------------------------------------------------

SPEC_RE = re.compile(r"^`ROADMAP:SPEC:(?P<id>\d+)` \*\*(?P<title>.+?)\*\* \[(?P<status>draft|active|retired)\]$")
MILESTONE_RE = re.compile(
    r"^## M(?P<num>\d+) — (?P<title>.+) \(`ROADMAP:MILESTONE:(?P<id>\d+)`, (?P<status>planned|active|done)\)$"
)
TASK_LINE_RE = re.compile(r"^\[(?P<box>.)\] (?P<rest>.*)$")
TASK_RE = re.compile(r"^`ROADMAP:TASK:(?P<id>\d+)` (?P<rest>.+)$")
SUFFIX_RE = re.compile(r"(?:^|\s)_\((?P<suffix>.*?)\)_(?=\s|$)")
SUFFIX_ORDER = ["implements", "depends on", "claimed by", "blocked"]
TITLE_PREFIXES = {"BUG", "PLACEHOLDER", "RECURRING", "BACKGROUND", "RESEARCH"}
SPEC_ID_RE = re.compile(r"^ROADMAP:SPEC:(\d+)$")
TASK_ID_RE = re.compile(r"^ROADMAP:TASK:(\d+)$")


@dataclass
class Task:
    id: int
    line: int
    box: str
    title: str
    implements: list[int] = field(default_factory=list)
    depends: list[int] = field(default_factory=list)
    claimed_by: str | None = None
    blocked: str | None = None
    milestone: int | None = None


def parse_suffix(report: Report, path: Path, line: int, suffix: str, task: Task) -> None:
    parts = suffix.split("; ")
    keys_seen: list[str] = []
    idx = 0
    while idx < len(parts):
        part = parts[idx]
        if part.startswith("blocked:"):
            key, value = "blocked", "; ".join(parts[idx:])[len("blocked:"):].strip()
            idx = len(parts)
        else:
            key = next((k for k in SUFFIX_ORDER[:3] if part.startswith(k + " ")), None)
            if key is None:
                report.error("roadmap.suffix", path, line,
                             f"unknown suffix element: {part!r} "
                             "(expected implements / depends on / claimed by / blocked:)")
                idx += 1
                continue
            value = part[len(key) + 1:].strip()
            idx += 1
        if key in keys_seen:
            report.error("roadmap.suffix", path, line, f"`{key}` repeated in the suffix")
            continue
        if keys_seen and SUFFIX_ORDER.index(key) < SUFFIX_ORDER.index(keys_seen[-1]):
            report.error("roadmap.suffix-order", path, line,
                         "suffix order: implements; depends on; claimed by; blocked:")
        keys_seen.append(key)
        if not value:
            report.error("roadmap.suffix", path, line, f"`{key}` without a value")
            continue
        if key in ("implements", "depends on"):
            id_re = SPEC_ID_RE if key == "implements" else TASK_ID_RE
            family = "ROADMAP:SPEC:n" if key == "implements" else "ROADMAP:TASK:n"
            target = task.implements if key == "implements" else task.depends
            for ref in (r.strip() for r in value.split(",")):
                mm = id_re.match(ref)
                if not mm:
                    report.error("roadmap.suffix-id", path, line, f"`{key}` expects `{family}`: {ref!r}")
                else:
                    target.append(int(mm.group(1)))
        elif key == "claimed by":
            task.claimed_by = value
        else:
            task.blocked = value


def check_roadmap(report: Report, root: Path, canon: dict[int, CanonEntry] | None = None) -> None:
    path = root / ".claude" / "roadmap.md"
    if not path.is_file():
        return
    text = read_text(report, path)
    if text is None:
        return
    lines = text.splitlines()

    first = next(((n, l) for n, l in enumerate(lines, 1) if l.strip()), None)
    if first is None or first[1].rstrip() != "# Roadmap":
        report.error("roadmap.title", path, first[0] if first else None, "the file must start with `# Roadmap`")

    specs: dict[int, int] = {}
    milestones: dict[int, tuple[int, str]] = {}
    milestone_tasks: dict[int, list[int]] = {}
    milestone_dod: dict[int, bool] = {}
    tasks: dict[int, Task] = {}

    section = None  # "specs" | "rules" | ("milestone", id) | "backlog"
    current_spec = None  # (id, line, has a Canon sub-bullet)
    current_task = None

    def close_spec():
        nonlocal current_spec
        if current_spec and not current_spec[2]:
            report.warn("roadmap.spec-canon", path, current_spec[1], "spec without a `- Canon: …` sub-bullet")
        current_spec = None

    def finish_task(t: Task | None):
        if t is None:
            return
        m = TASK_RE.match(t.title)
        if not m:
            report.error("roadmap.task", path, t.line, "malformed task: expected - [ ] `ROADMAP:TASK:n` Title _(…)_")
            return
        t.id = int(m.group("id"))
        rest = m.group("rest")
        sm = SUFFIX_RE.search(rest)
        title = rest[: sm.start()].strip() if sm else rest.strip()
        if sm:
            parse_suffix(report, path, t.line, sm.group("suffix"), t)
        elif "_(" in rest:
            report.error("roadmap.suffix", path, t.line, "suffix `_(` not closed by `)_`")
        if not title:
            report.error("roadmap.task", path, t.line, "empty task title")
        pm = re.match(r"^\[([^\]]+)\]", title)
        if pm and pm.group(1) not in TITLE_PREFIXES:
            report.warn("roadmap.title-prefix", path, t.line,
                        f"non-normalized title prefix: [{pm.group(1)}] (expected {sorted(TITLE_PREFIXES)})")
        t.title = title
        if t.id in tasks:
            report.error("roadmap.duplicate-id", path, t.line,
                         f"`ROADMAP:TASK:{t.id}` already used (line {tasks[t.id].line})")
            return
        tasks[t.id] = t
        if t.milestone is not None:
            milestone_tasks[t.milestone].append(t.id)

    for n, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if line.startswith("#"):
            close_spec()
            finish_task(current_task)
            current_task = None
            if line.startswith("## "):
                heading = line[3:].strip()
                if heading == "Specs":
                    section = "specs"
                elif heading == "Backlog (no milestone)":
                    section = "backlog"
                elif line.startswith("## M"):
                    m = MILESTONE_RE.match(line)
                    if not m:
                        report.error("roadmap.milestone", path, n,
                                     "malformed milestone heading: expected "
                                     "## M<n> — Title (`ROADMAP:MILESTONE:n`, planned|active|done)")
                        section = ("milestone", None)
                        continue
                    mid = int(m.group("id"))
                    if mid in milestones:
                        report.error("roadmap.duplicate-id", path, n,
                                     f"`ROADMAP:MILESTONE:{mid}` already used (line {milestones[mid][0]})")
                        section = ("milestone", None)
                        continue
                    if int(m.group("num")) != mid:
                        report.warn("roadmap.milestone-number", path, n,
                                    f"M{m.group('num')} carries the ID `ROADMAP:MILESTONE:{mid}`")
                    milestones[mid] = (n, m.group("status"))
                    milestone_tasks[mid] = []
                    milestone_dod[mid] = False
                    section = ("milestone", mid)
                else:
                    report.error("roadmap.section", path, n,
                                 f"unknown section: {heading!r} (expected Specs, M<n> — …, Backlog (no milestone))")
                    section = None
            elif not line.startswith("# ") or n != (first[0] if first else 0):
                report.error("roadmap.section", path, n, "heading outside the grammar (only `# Roadmap` and `## …`)")
            continue

        if not stripped:
            if current_task is not None:
                finish_task(current_task)
                current_task = None
            continue

        if section == "specs" or section == "rules":
            if line.startswith("- "):
                body = line[2:].strip()
                if body.startswith("`ROADMAP:SPEC:"):
                    close_spec()
                    if section == "rules":
                        report.error("roadmap.spec", path, n, "spec declared after `Rules:`")
                    m = SPEC_RE.match(body)
                    if not m:
                        report.error("roadmap.spec", path, n,
                                     "malformed spec: expected - `ROADMAP:SPEC:n` **Title** [draft|active|retired]")
                        continue
                    sid = int(m.group("id"))
                    if sid in specs:
                        report.error("roadmap.duplicate-id", path, n,
                                     f"`ROADMAP:SPEC:{sid}` already used (line {specs[sid]})")
                    else:
                        specs[sid] = n
                    current_spec = [sid, n, False]
                elif section == "rules":
                    pass  # rule
                else:
                    report.error("roadmap.spec", path, n, "bullet outside the grammar in Specs (spec or rule after `Rules:`)")
            elif line[0] in " \t" and current_spec is not None:
                if re.match(r"^-\s*Canon\s*:", stripped):
                    current_spec[2] = True
            elif stripped == "Rules:":
                close_spec()
                section = "rules"
            elif line[0] in " \t" and section == "rules":
                pass  # continuation of a rule
            else:
                report.error("roadmap.prose", path, n, f"text outside the grammar in Specs: {stripped[:60]!r}")
            continue

        if isinstance(section, tuple) or section == "backlog":
            mid = section[1] if isinstance(section, tuple) else None
            if line.startswith("- "):
                finish_task(current_task)
                current_task = None
                tm = TASK_LINE_RE.match(line[2:])
                if tm:
                    box = tm.group("box")
                    if box not in (" ", "~", "x"):
                        report.error("roadmap.checkbox", path, n, f"invalid checkbox `[{box}]` (expected [ ], [~], [x])")
                        continue
                    current_task = Task(id=-1, line=n, box=box, title=tm.group("rest"), milestone=mid)
                elif line[2:].lstrip().startswith("`ROADMAP:TASK:"):
                    report.error("roadmap.checkbox", path, n, "task without a checkbox [ ] / [~] / [x]")
                else:
                    report.warn("roadmap.bullet", path, n, "bullet that is not a task")
            elif line[0] in " \t" and current_task is not None:
                current_task.title += " " + stripped
            elif stripped.startswith("Milestone DoD:"):
                if mid is not None:
                    milestone_dod[mid] = True
            # the rest is the milestone description: free prose
            continue

        report.error("roadmap.prose", path, n, f"text outside a section: {stripped[:60]!r}")

    close_spec()
    finish_task(current_task)

    for mid, has_dod in milestone_dod.items():
        if not has_dod:
            report.warn("roadmap.milestone-dod", path, milestones[mid][0], "milestone without a `Milestone DoD: …` line")

    for t in tasks.values():
        if t.box == "~" and not t.claimed_by and not t.blocked:
            report.error("roadmap.claim-missing", path, t.line,
                         f"`ROADMAP:TASK:{t.id}` is [~] without `claimed by <user>` (nor `blocked:`)")
        if t.box == "x" and t.claimed_by:
            report.error("roadmap.claim-on-done", path, t.line,
                         f"`ROADMAP:TASK:{t.id}` is [x] but still carries `claimed by`")
        if t.box == " " and t.claimed_by:
            report.warn("roadmap.claim-on-todo", path, t.line,
                        f"`ROADMAP:TASK:{t.id}` is [ ] but carries `claimed by` (a claimed task is [~])")
        if t.box != "~" and t.blocked:
            report.warn("roadmap.blocked-not-in-progress", path, t.line,
                        f"`ROADMAP:TASK:{t.id}` carries `blocked:` without being [~]")
        for sid in t.implements:
            if sid not in specs:
                report.error("roadmap.unknown-ref", path, t.line,
                             f"`ROADMAP:TASK:{t.id}` implements a nonexistent `ROADMAP:SPEC:{sid}`")
        for dep in t.depends:
            if dep == t.id:
                report.error("roadmap.self-dependency", path, t.line, f"`ROADMAP:TASK:{t.id}` depends on itself")
            elif dep not in tasks:
                report.error("roadmap.unknown-ref", path, t.line,
                             f"`ROADMAP:TASK:{t.id}` depends on a nonexistent `ROADMAP:TASK:{dep}`")
            elif t.box in ("~", "x") and tasks[dep].box != "x":
                report.warn("roadmap.dependency-not-done", path, t.line,
                            f"`ROADMAP:TASK:{t.id}` is [{t.box}] while its dependency "
                            f"`ROADMAP:TASK:{dep}` is not [x]")

    # Dependency cycles.
    state: dict[int, int] = {}

    def visit(tid: int, stack: list[int]) -> None:
        state[tid] = 1
        for dep in tasks[tid].depends:
            if dep not in tasks or dep == tid:
                continue
            if state.get(dep) == 1:
                cycle = stack[stack.index(dep):] + [dep] if dep in stack else [tid, dep]
                report.error("roadmap.dependency-cycle", path, tasks[tid].line,
                             "dependency cycle: " + " → ".join(f"TASK:{c}" for c in cycle))
            elif state.get(dep) is None:
                visit(dep, stack + [dep])
        state[tid] = 2

    for tid in sorted(tasks):
        if tid not in state:
            visit(tid, [tid])

    for mid, (n, status) in milestones.items():
        if status == "done":
            undone = [tid for tid in milestone_tasks[mid] if tasks[tid].box != "x"]
            if undone:
                report.error("roadmap.milestone-done", path, n,
                             f"`ROADMAP:MILESTONE:{mid}` is done with tasks that are not [x]: "
                             + ", ".join(f"TASK:{t}" for t in undone))

    if canon is not None and (root / ".claude" / "canon").is_dir():
        for n, raw in enumerate(lines, start=1):
            for ref in CANON_REF_RE.findall(raw):
                if int(ref) not in canon:
                    report.warn("roadmap.unknown-canon-ref", path, n, f"reference to unknown `CANON:{ref}`")


# ---------------------------------------------------------------------------------------------


def validate(root: Path) -> Report:
    report = Report(root)
    check_manifests(report, root)
    check_frontmatters(report, root)
    check_model_mentions(report, root)
    canon = check_canon(report, root)
    check_roadmap(report, root, canon)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validates manifests, frontmatter, canon and roadmap.")
    parser.add_argument("root", nargs="?", default=".", help="project root (default: .)")
    parser.add_argument("--strict", action="store_true", help="warnings also make the run fail")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2
    report = validate(root)
    for f in report.findings:
        print(f)
    n_err, n_warn = len(report.errors), len(report.warnings)
    print(f"{n_err} error(s), {n_warn} warning(s)")
    if n_err or (args.strict and n_warn):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

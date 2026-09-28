#!/usr/bin/env python3
"""Validateur des fichiers du plugin roadmap (python3 stdlib uniquement).

Vérifie, sous une racine de projet :
  - les manifestes `.claude-plugin/marketplace.json` et `plugins/*/.claude-plugin/plugin.json` ;
  - le frontmatter des agents (`plugins/*/agents/*.md`) et skills (`plugins/*/skills/*/SKILL.md`) ;
  - la grammaire du canon (`.claude/canon/*.md`) ;
  - la grammaire de la roadmap (`.claude/roadmap.md`).

Chaque partie absente est ignorée : le script tourne aussi bien sur ce marketplace que sur un
projet qui ne fait qu'utiliser le plugin (canon + roadmap seulement).

La grammaire vérifiée est décrite dans `docs/grammar.md`, qui renvoie elle-même aux SKILL.md
(`canon-tracker`, `roadmap-tracker`) — seuls propriétaires de la grammaire (CANON:3).

Usage : python3 scripts/validate.py [RACINE] [--strict]
Code de sortie : 0 = aucune erreur, 1 = erreur(s) (ou avertissement(s) avec --strict), 2 = usage.
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
# Utilitaires
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
        report.error("io.unreadable", path, None, f"lecture impossible : {exc}")
        return None


def load_json(report: Report, path: Path):
    # CANON:4 — même critère que `python3 -c "import json; json.load(open(p))"`.
    text = read_text(report, path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        report.error("manifest.json", path, exc.lineno, f"JSON invalide : {exc.msg}")
        return None


# ---------------------------------------------------------------------------------------------
# Manifestes
# ---------------------------------------------------------------------------------------------


def check_manifests(report: Report, root: Path) -> None:
    plugin_manifests = sorted(root.glob("plugins/*/.claude-plugin/plugin.json"))
    plugins_by_dir: dict[Path, dict] = {}
    for path in plugin_manifests:
        data = load_json(report, path)
        if data is None:
            continue
        if not isinstance(data, dict):
            report.error("manifest.plugin", path, None, "la racine doit être un objet JSON")
            continue
        plugins_by_dir[path.parent.parent.resolve()] = data
        name = data.get("name")
        if not isinstance(name, str) or not name:
            report.error("manifest.plugin-name", path, None, "champ `name` requis (chaîne non vide)")
        version = data.get("version")
        if version is None:
            report.error("manifest.plugin-version", path, None, "champ `version` requis (semver)")
        elif not isinstance(version, str) or not SEMVER_RE.match(version):
            report.error("manifest.plugin-version", path, None, f"`version` n'est pas semver : {version!r}")

    mp_path = root / ".claude-plugin" / "marketplace.json"
    if not mp_path.is_file():
        return
    data = load_json(report, mp_path)
    if data is None:
        return
    if not isinstance(data, dict):
        report.error("manifest.marketplace", mp_path, None, "la racine doit être un objet JSON")
        return
    if not isinstance(data.get("name"), str) or not data.get("name"):
        report.error("manifest.marketplace-name", mp_path, None, "champ `name` requis")
    owner = data.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("name"), str) or not owner.get("name"):
        report.error("manifest.marketplace-owner", mp_path, None, "champ `owner.name` requis")
    version = data.get("version")
    if version is not None and (not isinstance(version, str) or not SEMVER_RE.match(version)):
        report.error("manifest.marketplace-version", mp_path, None, f"`version` n'est pas semver : {version!r}")
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        report.error("manifest.marketplace-plugins", mp_path, None, "champ `plugins` requis (liste)")
        return

    seen_names: set[str] = set()
    listed_dirs: set[Path] = set()
    for i, entry in enumerate(plugins):
        where = f"plugins[{i}]"
        if not isinstance(entry, dict):
            report.error("manifest.marketplace-entry", mp_path, None, f"{where} doit être un objet")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            report.error("manifest.marketplace-entry", mp_path, None, f"{where}.name requis")
            continue
        if name in seen_names:
            report.error("manifest.marketplace-duplicate", mp_path, None, f"plugin `{name}` listé deux fois")
        seen_names.add(name)
        source = entry.get("source")
        if source is None:
            report.error("manifest.marketplace-entry", mp_path, None, f"{where}.source requis")
            continue
        if not isinstance(source, str):
            continue  # source distante (objet github/url…) : hors du repo, rien à comparer
        if not source.startswith("./"):
            report.error("manifest.marketplace-source", mp_path, None,
                         f"{where}.source relatif doit commencer par `./` : {source!r}")
            continue
        plugin_dir = (root / source).resolve()
        listed_dirs.add(plugin_dir)
        manifest = plugin_dir / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            report.error("manifest.marketplace-source", mp_path, None,
                         f"{where}.source `{source}` ne contient pas `.claude-plugin/plugin.json`")
            continue
        pdata = plugins_by_dir.get(plugin_dir)
        if pdata is None:
            pdata = load_json(report, manifest)
        if isinstance(pdata, dict) and pdata.get("name") != name:
            report.error("manifest.name-mismatch", mp_path, None,
                         f"{where}.name `{name}` ≠ `name` de {source}/.claude-plugin/plugin.json "
                         f"(`{pdata.get('name')}`)")
        if isinstance(pdata, dict) and "version" in entry and entry["version"] != pdata.get("version"):
            report.error("manifest.version-mismatch", mp_path, None,
                         f"{where}.version `{entry['version']}` ≠ version de plugin.json "
                         f"(`{pdata.get('version')}`)")

    for plugin_dir in plugins_by_dir:
        if plugin_dir not in listed_dirs:
            report.warn("manifest.unlisted-plugin", plugin_dir / ".claude-plugin" / "plugin.json", None,
                        "plugin absent du catalogue `.claude-plugin/marketplace.json`")


# ---------------------------------------------------------------------------------------------
# Frontmatter agents / skills
# ---------------------------------------------------------------------------------------------

MODEL_ALIASES = {"opus", "sonnet", "haiku", "fable", "inherit"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
PLUGIN_AGENT_IGNORED = ("hooks", "mcpServers", "permissionMode")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FM_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:(?:\s+(.*?))?\s*$")


def _scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    # Commentaire en fin de ligne d'un scalaire nu.
    return re.sub(r"\s+#.*$", "", raw)


def parse_frontmatter(text: str):
    """Mini-parseur YAML pour frontmatter : clés de premier niveau, scalaires, blocs `|`/`>`.

    Retourne (dict clé -> (valeur, ligne), ligne de fin) ou (None, message d'erreur).
    Les valeurs imbriquées (listes, maps) sont rendues sous forme de texte brut.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "frontmatter absent (le fichier doit commencer par `---`)"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, "frontmatter non fermé (`---` final manquant)"
    data: dict[str, tuple[str, int]] = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":
            return None, f"ligne {i + 1} : indentation inattendue hors d'une valeur"
        m = FM_KEY_RE.match(line)
        if not m:
            return None, f"ligne {i + 1} : `clé: valeur` attendu"
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
            return None, f"ligne {start} : clé `{key}` dupliquée"
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
            report.error(f"frontmatter.{key}", path, None, f"champ `{key}` requis")
    if "name" in data:
        name, line = data["name"]
        if name and not NAME_RE.match(name):
            report.warn("frontmatter.name-format", path, line,
                        f"`name` devrait être en minuscules/chiffres/tirets : {name!r}")
        if kind == "skill" and name and name != path.parent.name:
            report.warn("frontmatter.name-dir", path, line,
                        f"`name` ({name}) ≠ nom du dossier du skill ({path.parent.name})")
    if "model" in data:
        model, line = data["model"]
        if model not in MODEL_ALIASES and not re.match(r"^claude-[a-z0-9][a-z0-9.\-\[\]]*$", model):
            report.error("frontmatter.model", path, line,
                         f"`model` invalide : {model!r} (attendu {sorted(MODEL_ALIASES)} ou un ID `claude-*`)")
    if "effort" in data:
        effort, line = data["effort"]
        if effort not in EFFORTS:
            report.error("frontmatter.effort", path, line,
                         f"`effort` invalide : {effort!r} (attendu {sorted(EFFORTS)})")
    if kind == "agent":
        for key in PLUGIN_AGENT_IGNORED:
            if key in data:
                report.warn("frontmatter.plugin-agent-ignored", path, data[key][1],
                            f"`{key}` est ignoré par Claude Code pour un agent livré par un plugin")


def check_frontmatters(report: Report, root: Path) -> None:
    for path in sorted(root.glob("plugins/*/agents/*.md")):
        check_frontmatter_file(report, path, "agent")
    for path in sorted(root.glob("plugins/*/skills/*/SKILL.md")):
        check_frontmatter_file(report, path, "skill")


# ---------------------------------------------------------------------------------------------
# Canon — grammaire : skill canon-tracker, § « Grammaire d'une entrée »
# ---------------------------------------------------------------------------------------------

CANON_HEAD = (
    r"`CANON:(?P<id>\d+)` \[(?:USER:(?P<user>\S(?:[^\]]*?\S)?)|(?P<model>MODEL)) (?P<date>" + DATE + r")\]"
)
CANON_LIVE_RE = re.compile(r"^" + CANON_HEAD + r" (?P<text>\S.*)$")
CANON_HEAD_RE = re.compile(r"^" + CANON_HEAD + r"(?P<rest>.*)$")
OBSOLETE_RE = re.compile(r"—\s*obsolète\s+(?P<date>" + DATE + r")\s*:\s*(?P<reason>\S.*)$")
PROMOTED = "(promu de MODEL)"
CANON_REF_RE = re.compile(r"\bCANON:(\d+)\b")


@dataclass
class CanonEntry:
    id: int
    path: Path
    line: int
    deprecated: bool
    text: str


def _blocks(lines: list[str]):
    """Découpe en blocs de liste de premier niveau : (ligne, texte joint) ; plus la prose isolée."""
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
            report.error("canon.strike", path, line, "`~~` ouvrant sans `~~` fermant")
            return None
        inner, after = text[2:close], text[close + 2:]
        m = CANON_LIVE_RE.match(inner)
        if not m:
            report.error("canon.entry", path, line,
                         "entrée barrée mal formée : attendu ~~`CANON:n` [USER:<nom> AAAA-MM-JJ|MODEL AAAA-MM-JJ] <point>~~")
            return None
        body, deprecated = m.group("text"), True
    else:
        m = CANON_HEAD_RE.match(text)
        if not m:
            report.error("canon.entry", path, line,
                         "entrée mal formée : attendu `CANON:n` [USER:<nom> AAAA-MM-JJ] <point> "
                         "ou `CANON:n` [MODEL AAAA-MM-JJ] <point>")
            return None
        rest = m.group("rest")
        if not rest.startswith(" ") or not rest.strip():
            report.error("canon.entry", path, line, "le point de l'entrée est vide")
            return None
        body = rest.strip()
        deprecated = body.startswith("~~")
        after = ""
        if deprecated:
            # Seconde lecture de « barrer le texte » : seul le point est barré, l'en-tête reste.
            close = body.find("~~", 2)
            if close == -1:
                report.error("canon.strike", path, line, "`~~` ouvrant sans `~~` fermant")
                return None
            body, after = body[2:close], body[close + 2:]
            if not body.strip():
                report.error("canon.entry", path, line, "le point barré est vide")
                return None

    cid = int(m.group("id"))
    date = m.group("date")
    if not valid_date(date):
        report.error("canon.date", path, line, f"date invalide : {date}")

    obsolete = OBSOLETE_RE.search(after if deprecated else body)
    if deprecated:
        if not obsolete:
            report.error("canon.obsolete-missing", path, line,
                         "entrée barrée sans `— obsolète AAAA-MM-JJ : <raison>` (en fin de ligne ou en dessous)")
        else:
            odate = obsolete.group("date")
            if not valid_date(odate):
                report.error("canon.date", path, line, f"date d'obsolescence invalide : {odate}")
            elif valid_date(date) and odate < date:
                report.warn("canon.obsolete-before-entry", path, line,
                            f"obsolète le {odate}, avant la date de l'entrée ({date})")
        stray_after = OBSOLETE_RE.sub("", after).strip() if obsolete else after.strip()
        if stray_after:
            report.error("canon.entry", path, line, f"texte hors grammaire après l'entrée barrée : {stray_after!r}")
    elif obsolete:
        report.error("canon.obsolete-unstruck", path, line,
                     "marque `— obsolète …` sur une entrée non barrée (barrer le texte avec `~~…~~`)")
    elif "~~" in body:
        report.error("canon.strike", path, line, "`~~` au milieu d'une entrée : barrer le point en entier")

    if body.rstrip().endswith(PROMOTED) and m.group("model"):
        report.error("canon.promotion", path, line, f"`{PROMOTED}` sur une entrée [MODEL]")
    return CanonEntry(cid, path, line, deprecated, text)


def check_canon(report: Report, root: Path) -> dict[int, CanonEntry]:
    canon_dir = root / ".claude" / "canon"
    entries: dict[int, CanonEntry] = {}
    if not canon_dir.is_dir():
        return entries
    files = sorted(canon_dir.glob("*.md"))
    for path in files:
        if path.name == "divers.md":
            report.error("canon.divers", path, None,
                         "jamais de `divers.md` : une entrée qui ne rentre nulle part signale un thème à nommer")
        text = read_text(report, path)
        if text is None:
            continue
        lines = text.splitlines()
        blocks, stray, headings = _blocks(lines)
        first = next(((n, l) for n, l in enumerate(lines, 1) if l.strip()), None)
        if first is None or not re.match(r"^# \S", first[1]):
            report.error("canon.title", path, first[0] if first else None,
                         "le fichier doit commencer par un titre `# <Thème>`")
        for n, line in stray:
            report.error("canon.prose", path, n, f"prose hors entrée : {line.strip()[:60]!r}")
        for n, text in blocks:
            entry = parse_canon_entry(report, path, n, text)
            if entry is None:
                continue
            if entry.id in entries:
                prev = entries[entry.id]
                rel = prev.path.name
                report.error("canon.duplicate-id", path, n,
                             f"`CANON:{entry.id}` déjà utilisé ({rel}:{prev.line}) — IDs uniques sur tout le dossier")
            else:
                entries[entry.id] = entry
    # Références croisées : un `CANON:n` cité doit exister.
    for entry in entries.values():
        for ref in CANON_REF_RE.findall(entry.text):
            if int(ref) not in entries:
                report.warn("canon.unknown-ref", entry.path, entry.line, f"référence à `CANON:{ref}` inexistant")
    return entries


# ---------------------------------------------------------------------------------------------
# Roadmap — grammaire : skill roadmap-tracker, § « Grammaire du fichier »
# ---------------------------------------------------------------------------------------------

SPEC_RE = re.compile(r"^`ROADMAP:SPEC:(?P<id>\d+)` \*\*(?P<title>.+?)\*\* \[(?P<status>draft|active|retired)\]$")
MILESTONE_RE = re.compile(
    r"^## M(?P<num>\d+) — (?P<title>.+) \(`ROADMAP:MILESTONE:(?P<id>\d+)`, (?P<status>planned|active|done)\)$"
)
TASK_LINE_RE = re.compile(r"^\[(?P<box>.)\] (?P<rest>.*)$")
TASK_RE = re.compile(r"^`ROADMAP:TASK:(?P<id>\d+)` (?P<rest>.+)$")
SUFFIX_RE = re.compile(r"(?:^|\s)_\((?P<suffix>.*?)\)_(?=\s|$)")
SUFFIX_ORDER = ["implements", "depends on", "claimed by", "blocked"]
TITLE_PREFIXES = {"BUG", "JALON", "RÉCURRENT", "FOND", "RÉFLEXION"}
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
                             f"élément de suffixe inconnu : {part!r} "
                             "(attendu implements / depends on / claimed by / blocked:)")
                idx += 1
                continue
            value = part[len(key) + 1:].strip()
            idx += 1
        if key in keys_seen:
            report.error("roadmap.suffix", path, line, f"`{key}` répété dans le suffixe")
            continue
        if keys_seen and SUFFIX_ORDER.index(key) < SUFFIX_ORDER.index(keys_seen[-1]):
            report.error("roadmap.suffix-order", path, line,
                         "ordre du suffixe : implements ; depends on ; claimed by ; blocked:")
        keys_seen.append(key)
        if not value:
            report.error("roadmap.suffix", path, line, f"`{key}` sans valeur")
            continue
        if key in ("implements", "depends on"):
            id_re = SPEC_ID_RE if key == "implements" else TASK_ID_RE
            family = "ROADMAP:SPEC:n" if key == "implements" else "ROADMAP:TASK:n"
            target = task.implements if key == "implements" else task.depends
            for ref in (r.strip() for r in value.split(",")):
                mm = id_re.match(ref)
                if not mm:
                    report.error("roadmap.suffix-id", path, line, f"`{key}` attend des `{family}` : {ref!r}")
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
        report.error("roadmap.title", path, first[0] if first else None, "le fichier doit commencer par `# Roadmap`")

    specs: dict[int, int] = {}
    milestones: dict[int, tuple[int, str]] = {}
    milestone_tasks: dict[int, list[int]] = {}
    milestone_dod: dict[int, bool] = {}
    tasks: dict[int, Task] = {}

    section = None  # "specs" | "rules" | ("milestone", id) | "backlog"
    current_spec = None  # (id, ligne, a une sous-puce Canon)
    current_task = None

    def close_spec():
        nonlocal current_spec
        if current_spec and not current_spec[2]:
            report.warn("roadmap.spec-canon", path, current_spec[1], "spec sans sous-puce `- Canon : …`")
        current_spec = None

    def finish_task(t: Task | None):
        if t is None:
            return
        m = TASK_RE.match(t.title)
        if not m:
            report.error("roadmap.task", path, t.line, "tâche mal formée : attendu - [ ] `ROADMAP:TASK:n` Titre _(…)_")
            return
        t.id = int(m.group("id"))
        rest = m.group("rest")
        sm = SUFFIX_RE.search(rest)
        title = rest[: sm.start()].strip() if sm else rest.strip()
        if sm:
            parse_suffix(report, path, t.line, sm.group("suffix"), t)
        elif "_(" in rest:
            report.error("roadmap.suffix", path, t.line, "suffixe `_(` non fermé par `)_`")
        if not title:
            report.error("roadmap.task", path, t.line, "titre de tâche vide")
        pm = re.match(r"^\[([^\]]+)\]", title)
        if pm and pm.group(1) not in TITLE_PREFIXES:
            report.warn("roadmap.title-prefix", path, t.line,
                        f"préfixe de titre non normalisé : [{pm.group(1)}] (attendu {sorted(TITLE_PREFIXES)})")
        t.title = title
        if t.id in tasks:
            report.error("roadmap.duplicate-id", path, t.line,
                         f"`ROADMAP:TASK:{t.id}` déjà utilisé (ligne {tasks[t.id].line})")
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
                                     "en-tête de milestone mal formé : attendu "
                                     "## M<n> — Titre (`ROADMAP:MILESTONE:n`, planned|active|done)")
                        section = ("milestone", None)
                        continue
                    mid = int(m.group("id"))
                    if mid in milestones:
                        report.error("roadmap.duplicate-id", path, n,
                                     f"`ROADMAP:MILESTONE:{mid}` déjà utilisé (ligne {milestones[mid][0]})")
                        section = ("milestone", None)
                        continue
                    if int(m.group("num")) != mid:
                        report.warn("roadmap.milestone-number", path, n,
                                    f"M{m.group('num')} porte l'ID `ROADMAP:MILESTONE:{mid}`")
                    milestones[mid] = (n, m.group("status"))
                    milestone_tasks[mid] = []
                    milestone_dod[mid] = False
                    section = ("milestone", mid)
                else:
                    report.error("roadmap.section", path, n,
                                 f"section inconnue : {heading!r} (attendu Specs, M<n> — …, Backlog (no milestone))")
                    section = None
            elif not line.startswith("# ") or n != (first[0] if first else 0):
                report.error("roadmap.section", path, n, "titre hors grammaire (seuls `# Roadmap` et `## …`)")
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
                        report.error("roadmap.spec", path, n, "spec déclarée après `Règles :`")
                    m = SPEC_RE.match(body)
                    if not m:
                        report.error("roadmap.spec", path, n,
                                     "spec mal formée : attendu - `ROADMAP:SPEC:n` **Titre** [draft|active|retired]")
                        continue
                    sid = int(m.group("id"))
                    if sid in specs:
                        report.error("roadmap.duplicate-id", path, n,
                                     f"`ROADMAP:SPEC:{sid}` déjà utilisé (ligne {specs[sid]})")
                    else:
                        specs[sid] = n
                    current_spec = [sid, n, False]
                elif section == "rules":
                    pass  # règle
                else:
                    report.error("roadmap.spec", path, n, "puce hors grammaire dans Specs (spec ou règle après `Règles :`)")
            elif line[0] in " \t" and current_spec is not None:
                if re.match(r"^-\s*Canon\s*:", stripped):
                    current_spec[2] = True
            elif stripped == "Règles :":
                close_spec()
                section = "rules"
            elif line[0] in " \t" and section == "rules":
                pass  # continuation d'une règle
            else:
                report.error("roadmap.prose", path, n, f"texte hors grammaire dans Specs : {stripped[:60]!r}")
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
                        report.error("roadmap.checkbox", path, n, f"case invalide `[{box}]` (attendu [ ], [~], [x])")
                        continue
                    current_task = Task(id=-1, line=n, box=box, title=tm.group("rest"), milestone=mid)
                elif line[2:].lstrip().startswith("`ROADMAP:TASK:"):
                    report.error("roadmap.checkbox", path, n, "tâche sans case [ ] / [~] / [x]")
                else:
                    report.warn("roadmap.bullet", path, n, "puce qui n'est pas une tâche")
            elif line[0] in " \t" and current_task is not None:
                current_task.title += " " + stripped
            elif stripped.startswith("DoD du milestone :"):
                if mid is not None:
                    milestone_dod[mid] = True
            # le reste = description du milestone, prose libre
            continue

        report.error("roadmap.prose", path, n, f"texte hors section : {stripped[:60]!r}")

    close_spec()
    finish_task(current_task)

    for mid, has_dod in milestone_dod.items():
        if not has_dod:
            report.warn("roadmap.milestone-dod", path, milestones[mid][0], "milestone sans ligne `DoD du milestone : …`")

    for t in tasks.values():
        if t.box == "~" and not t.claimed_by and not t.blocked:
            report.error("roadmap.claim-missing", path, t.line,
                         f"`ROADMAP:TASK:{t.id}` est [~] sans `claimed by <user>` (ni `blocked:`)")
        if t.box == "x" and t.claimed_by:
            report.error("roadmap.claim-on-done", path, t.line,
                         f"`ROADMAP:TASK:{t.id}` est [x] mais porte encore `claimed by`")
        if t.box == " " and t.claimed_by:
            report.warn("roadmap.claim-on-todo", path, t.line,
                        f"`ROADMAP:TASK:{t.id}` est [ ] mais porte `claimed by` (une tâche claimée est [~])")
        if t.box != "~" and t.blocked:
            report.warn("roadmap.blocked-not-in-progress", path, t.line,
                        f"`ROADMAP:TASK:{t.id}` porte `blocked:` sans être [~]")
        for sid in t.implements:
            if sid not in specs:
                report.error("roadmap.unknown-ref", path, t.line,
                             f"`ROADMAP:TASK:{t.id}` implements `ROADMAP:SPEC:{sid}` inexistante")
        for dep in t.depends:
            if dep == t.id:
                report.error("roadmap.self-dependency", path, t.line, f"`ROADMAP:TASK:{t.id}` dépend d'elle-même")
            elif dep not in tasks:
                report.error("roadmap.unknown-ref", path, t.line,
                             f"`ROADMAP:TASK:{t.id}` depends on `ROADMAP:TASK:{dep}` inexistante")
            elif t.box in ("~", "x") and tasks[dep].box != "x":
                report.warn("roadmap.dependency-not-done", path, t.line,
                            f"`ROADMAP:TASK:{t.id}` est [{t.box}] alors que sa dépendance "
                            f"`ROADMAP:TASK:{dep}` n'est pas [x]")

    # Cycles de dépendances.
    state: dict[int, int] = {}

    def visit(tid: int, stack: list[int]) -> None:
        state[tid] = 1
        for dep in tasks[tid].depends:
            if dep not in tasks or dep == tid:
                continue
            if state.get(dep) == 1:
                cycle = stack[stack.index(dep):] + [dep] if dep in stack else [tid, dep]
                report.error("roadmap.dependency-cycle", path, tasks[tid].line,
                             "cycle de dépendances : " + " → ".join(f"TASK:{c}" for c in cycle))
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
                             f"`ROADMAP:MILESTONE:{mid}` est done avec des tâches non [x] : "
                             + ", ".join(f"TASK:{t}" for t in undone))

    if canon is not None and (root / ".claude" / "canon").is_dir():
        for n, raw in enumerate(lines, start=1):
            for ref in CANON_REF_RE.findall(raw):
                if int(ref) not in canon:
                    report.warn("roadmap.unknown-canon-ref", path, n, f"référence à `CANON:{ref}` inexistant")


# ---------------------------------------------------------------------------------------------


def validate(root: Path) -> Report:
    report = Report(root)
    check_manifests(report, root)
    check_frontmatters(report, root)
    canon = check_canon(report, root)
    check_roadmap(report, root, canon)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valide manifestes, frontmatter, canon et roadmap.")
    parser.add_argument("root", nargs="?", default=".", help="racine du projet (défaut : .)")
    parser.add_argument("--strict", action="store_true", help="les avertissements font aussi échouer")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"racine introuvable : {root}", file=sys.stderr)
        return 2
    report = validate(root)
    for f in report.findings:
        print(f)
    n_err, n_warn = len(report.errors), len(report.warnings)
    print(f"{n_err} erreur(s), {n_warn} avertissement(s)")
    if n_err or (args.strict and n_warn):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

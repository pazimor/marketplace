#!/usr/bin/env python3
"""Audit d'usage des skills et agents d'un projet Claude Code, depuis ses transcripts.

Lit ~/.claude/projects/<slug>/**/*.jsonl (sessions + sous-agents) et compte :
  - skills : appels à l'outil Skill, /commandes tapées, lectures directes de SKILL.md
  - agents : appels à l'outil Agent/Task par subagent_type
  - mentions (option --mention) : citations d'un nom dans le texte user/assistant,
    listes de skills injectées par le système exclues

Un « 0 appel » veut dire que le skill n'a jamais été chargé, pas qu'il n'a jamais
influencé une réponse (son contenu a pu être recopié ailleurs). Seules les sessions
de la machine locale sont vues.

Usage :
  python3 tools/skill_audit.py                       # projet = dossier courant
  python3 tools/skill_audit.py --project ~/Test_starship
  python3 tools/skill_audit.py --exclude <session-id> --mention Fight-Mechanics
  python3 tools/skill_audit.py --json > audit.json
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

SKILL_MD = re.compile(r"skills/([A-Za-z0-9_:\-]+)/SKILL\.md")
COMMAND = re.compile(r"<command-name>/?([^<]+)</command-name>")
REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def project_slug(path):
    # Claude Code remplace tout caractère non alphanumérique par « - »
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(os.path.expanduser(path)))


def new_entry():
    return {"n": 0, "sessions": set(), "first": None, "last": None, "via": collections.Counter()}


def hit(table, name, session, ts, via=None):
    e = table[name]
    e["n"] += 1
    e["sessions"].add(session)
    if ts:
        day = ts[:10]
        e["first"] = min(e["first"] or day, day)
        e["last"] = max(e["last"] or day, day)
    if via:
        e["via"][via] += 1


def blocks(message):
    content = (message or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def audit(root, exclude, mentions):
    skills = collections.defaultdict(new_entry)
    agents = collections.defaultdict(new_entry)
    cited = collections.defaultdict(new_entry)
    days = []
    files = sorted(set(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)))
    for path in files:
        session = os.path.relpath(path, root).split(os.sep)[0].removesuffix(".jsonl")
        if session in exclude:
            continue
        with open(path, errors="ignore") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = rec.get("timestamp", "")
                if ts:
                    days.append(ts[:10])
                role = rec.get("type")
                for b in blocks(rec.get("message")):
                    if b.get("type") == "tool_use":
                        inp = b.get("input") or {}
                        name = b.get("name")
                        if name == "Skill":
                            hit(skills, inp.get("skill") or inp.get("command", "?"), session, ts, "Skill")
                        elif name in ("Agent", "Task"):
                            hit(agents, inp.get("subagent_type") or "general-purpose", session, ts)
                        elif name == "Read":
                            for s in SKILL_MD.findall(inp.get("file_path", "")):
                                hit(skills, s, session, ts, "Read SKILL.md")
                        elif name == "Bash":
                            for s in set(SKILL_MD.findall(inp.get("command", ""))):
                                hit(skills, s, session, ts, "bash SKILL.md")
                    elif b.get("type") == "text":
                        text = b.get("text", "")
                        if role == "user":
                            for c in COMMAND.findall(text):
                                hit(skills, c.strip(), session, ts, "slash")
                        if mentions:
                            text = REMINDER.sub("", text)
                            for m in mentions:
                                if m in text:
                                    hit(cited, m, session, ts, role)
    return {
        "period": [min(days), max(days)] if days else None,
        "files": len(files),
        "skills": skills,
        "agents": agents,
        "mentions": cited,
    }


def serialisable(table):
    return {
        k: {**v, "sessions": len(v["sessions"]), "via": dict(v["via"])}
        for k, v in sorted(table.items(), key=lambda kv: -kv[1]["n"])
    }


def print_table(title, table):
    print(f"\n== {title} ==")
    for k, v in serialisable(table).items():
        via = f" {v['via']}" if v["via"] else ""
        print(f"{k:45} n={v['n']:4} sess={v['sessions']:3} {v['first']}..{v['last']}{via}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".", help="dossier du projet (défaut : dossier courant)")
    ap.add_argument("--exclude", action="append", default=[], help="id de session à ignorer (répétable)")
    ap.add_argument("--mention", action="append", default=[], help="nom à chercher dans le texte (répétable)")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args()

    root = os.path.expanduser(os.path.join("~/.claude/projects", project_slug(args.project)))
    if not os.path.isdir(root):
        sys.exit(f"aucun transcript : {root}")
    res = audit(root, set(args.exclude), args.mention)

    if args.json:
        json.dump({**res, **{k: serialisable(res[k]) for k in ("skills", "agents", "mentions")}},
                  sys.stdout, indent=2, ensure_ascii=False)
        return
    print(f"transcripts : {root}")
    print(f"période {res['period'][0]} .. {res['period'][1]} — {res['files']} fichiers" if res["period"] else "vide")
    print_table("SKILLS", res["skills"])
    print_table("AGENTS", res["agents"])
    if args.mention:
        print_table("MENTIONS", res["mentions"])


if __name__ == "__main__":
    main()

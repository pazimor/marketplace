"""Validator tests (unittest, stdlib only).

Run from the repo root: python3 -m unittest discover -s scripts/tests -v
"""

import io
import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import validate  # noqa: E402

VALID_CANON = {
    "tests.md": """\
        # Tests

        - `CANON:12` [USER:pazimor 2026-08-14] The suite runs with `pytest -q` from the
          repo root; never from a subfolder (the fixtures break).
        - `CANON:13` [MODEL 2026-08-14] `pytest -q tests/test_graph.py` takes ~40 s.
        - `CANON:14` [USER:pazimor 2026-08-20] A test that touches the network is rejected in
          review, even when marked `skip`. (promoted from MODEL)
        - ~~`CANON:9` [MODEL 2026-07-02] The tests run via `make test`.~~
          — obsolete 2026-08-14: `make test` was removed, replaced by `CANON:12`.
        """,
    "invariants.md": """\
        # Invariants

        - `CANON:1` [USER:pazimor 2026-09-01] No dependency on a third-party service.
        - `CANON:2` [MODEL 2026-09-01] ~~Only the point is struck through.~~ — obsolete 2026-09-02: replaced by `CANON:1`.
        """,
    "expectations.md": "# Expectations\n",
}

VALID_ROADMAP = """\
    # Roadmap

    ## Specs

    - `ROADMAP:SPEC:1` **Spec title** [active]
      - Canon: the settled design, on
        two lines.

    Rules:
    - rule 1
    - rule 2

    ## M1 — First (`ROADMAP:MILESTONE:1`, done)

    Dated description — sponsor decision 2026-07-30.

    Milestone DoD: observable criterion.

    - [x] `ROADMAP:TASK:1` Title _(implements ROADMAP:SPEC:1)_
    - [x] `ROADMAP:TASK:2` [BUG] Title _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:1)_ — dated note

    ## M2 — Second (`ROADMAP:MILESTONE:2`, active)

    Milestone DoD: other criterion.

    - [~] `ROADMAP:TASK:3` Title _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:1, ROADMAP:TASK:2; claimed by pazimor)_
    - [~] `ROADMAP:TASK:4` Title _(blocked: waiting for an answer; with a semicolon)_
    - [ ] `ROADMAP:TASK:5` Title _(depends on ROADMAP:TASK:3)_

    ## Backlog (no milestone)

    - [ ] `ROADMAP:TASK:6` [RESEARCH] Idea
    """

AGENT = """\
    ---
    name: orchestrator
    description: >-
      Entry point, on
      several lines.
    model: sonnet
    effort: high
    # comment
    ---

    Body.
    """

SKILL = """\
    ---
    name: roadmap-tracker
    description: Maintain the roadmap.
    ---

    # Body
    """


def dedent(s):
    return textwrap.dedent(s)


class Fixture:
    """Builds a valid temporary project, then lets a test break part of it."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write(".claude-plugin/marketplace.json", json.dumps({
            "name": "marketplace",
            "owner": {"name": "pazimor"},
            "version": "0.3.0",
            "plugins": [{"name": "orchestration", "source": "./plugins/orchestration", "description": "x"}],
        }))
        self.write("plugins/orchestration/.claude-plugin/plugin.json",
                   json.dumps({"name": "orchestration", "version": "0.2.0"}))
        self.write("plugins/orchestration/agents/orchestrator.md", dedent(AGENT))
        self.write("plugins/orchestration/skills/roadmap-tracker/SKILL.md", dedent(SKILL))
        for name, body in VALID_CANON.items():
            self.write(f".claude/canon/{name}", dedent(body))
        self.write(".claude/roadmap.md", dedent(VALID_ROADMAP))

    def write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def replace(self, rel, old, new):
        text = self.read(rel)
        assert old in text, f"{old!r} not found in {rel}"
        self.write(rel, text.replace(old, new, 1))

    def cleanup(self):
        self.tmp.cleanup()


class Base(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.cleanup)

    def run_validate(self):
        return validate.validate(self.fx.root)

    def assertError(self, code):
        report = self.run_validate()
        self.assertIn(code, report.codes(validate.ERROR), "\n".join(map(str, report.findings)))
        return report

    def assertWarning(self, code):
        report = self.run_validate()
        self.assertIn(code, report.codes(validate.WARNING), "\n".join(map(str, report.findings)))
        self.assertEqual(report.errors, [], "\n".join(map(str, report.errors)))
        return report


class TestValidFixture(Base):
    def test_valid_project_has_no_findings(self):
        report = self.run_validate()
        self.assertEqual(report.findings, [], "\n".join(map(str, report.findings)))

    def test_main_exit_codes(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(validate.main([str(self.fx.root)]), 0)
            self.fx.replace(".claude/roadmap.md", "claimed by pazimor", "")
            self.assertEqual(validate.main([str(self.fx.root)]), 1)
            self.assertEqual(validate.main([str(self.fx.root / "absent")]), 2)

    def test_strict_fails_on_warnings(self):
        self.fx.write("plugins/orchestration/agents/orchestrator.md", dedent(AGENT).replace("effort: high", "hooks: {}"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(validate.main([str(self.fx.root)]), 0)
            self.assertEqual(validate.main([str(self.fx.root), "--strict"]), 1)

    def test_empty_project_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(validate.validate(Path(d)).findings, [])

    def test_consumer_project_without_manifests(self):
        # A project that only uses the plugin: canon + roadmap, no manifest.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".claude" / "canon").mkdir(parents=True)
            (root / ".claude" / "canon" / "tests.md").write_text(dedent(VALID_CANON["tests.md"]), encoding="utf-8")
            (root / ".claude" / "roadmap.md").write_text("# Roadmap\n\n## Backlog (no milestone)\n", encoding="utf-8")
            self.assertEqual(validate.validate(root).findings, [])


class TestManifests(Base):
    def test_invalid_json(self):
        self.fx.write("plugins/orchestration/.claude-plugin/plugin.json", '{"name": "orchestration",}')
        self.assertError("manifest.json")

    def test_missing_version(self):
        self.fx.write("plugins/orchestration/.claude-plugin/plugin.json", json.dumps({"name": "orchestration"}))
        self.assertError("manifest.plugin-version")

    def test_non_semver_version(self):
        self.fx.write("plugins/orchestration/.claude-plugin/plugin.json", json.dumps({"name": "orchestration", "version": "1.2"}))
        self.assertError("manifest.plugin-version")

    def test_missing_plugin_name(self):
        self.fx.write("plugins/orchestration/.claude-plugin/plugin.json", json.dumps({"version": "1.0.0"}))
        self.assertError("manifest.plugin-name")

    def test_name_mismatch(self):
        self.fx.write("plugins/orchestration/.claude-plugin/plugin.json", json.dumps({"name": "other", "version": "1.0.0"}))
        self.assertError("manifest.name-mismatch")

    def test_missing_owner(self):
        data = json.loads(self.fx.read(".claude-plugin/marketplace.json"))
        del data["owner"]
        self.fx.write(".claude-plugin/marketplace.json", json.dumps(data))
        self.assertError("manifest.marketplace-owner")

    def test_bad_source(self):
        data = json.loads(self.fx.read(".claude-plugin/marketplace.json"))
        data["plugins"][0]["source"] = "./plugins/missing"
        self.fx.write(".claude-plugin/marketplace.json", json.dumps(data))
        self.assertError("manifest.marketplace-source")

    def test_unlisted_plugin_warns(self):
        self.fx.write("plugins/extra/.claude-plugin/plugin.json", json.dumps({"name": "extra", "version": "0.1.0"}))
        self.assertWarning("manifest.unlisted-plugin")


class TestFrontmatter(Base):
    AGENT_PATH = "plugins/orchestration/agents/orchestrator.md"
    SKILL_PATH = "plugins/orchestration/skills/roadmap-tracker/SKILL.md"

    def test_missing_frontmatter(self):
        self.fx.write(self.SKILL_PATH, "# No frontmatter\n")
        self.assertError("frontmatter.syntax")

    def test_unclosed_frontmatter(self):
        self.fx.write(self.SKILL_PATH, "---\nname: roadmap-tracker\ndescription: x\n")
        self.assertError("frontmatter.syntax")

    def test_missing_description(self):
        self.fx.write(self.SKILL_PATH, "---\nname: roadmap-tracker\n---\n")
        self.assertError("frontmatter.description")

    def test_missing_name(self):
        self.fx.replace(self.AGENT_PATH, "name: orchestrator\n", "")
        self.assertError("frontmatter.name")

    def test_bad_model(self):
        self.fx.replace(self.AGENT_PATH, "model: sonnet", "model: gpt-5")
        self.assertError("frontmatter.model")

    def test_model_id_accepted(self):
        self.fx.replace(self.AGENT_PATH, "model: sonnet", "model: claude-opus-4-8[1m]")
        self.assertEqual(self.run_validate().findings, [])

    def test_quoted_model_accepted(self):
        self.fx.replace(self.AGENT_PATH, "model: sonnet", 'model: "haiku"')
        self.assertEqual(self.run_validate().findings, [])

    def test_agent_without_model_ok(self):
        for line in ("", "model: inherit\n", "model: fable\n"):
            with self.subTest(line=line):
                self.fx.write(self.AGENT_PATH, dedent(AGENT).replace("model: sonnet\n", line))
                self.assertEqual(self.run_validate().findings, [])

    def test_skill_without_model_ok(self):
        self.assertNotIn("model:", self.fx.read(self.SKILL_PATH))
        self.assertEqual(self.run_validate().findings, [])

    def test_model_named_in_agent_body(self):
        self.fx.replace(self.AGENT_PATH, "Body.", "Delegates to Opus.")
        self.assertError("plugin.model-mention")

    def test_model_named_in_description(self):
        self.fx.replace(self.AGENT_PATH, "several lines.", "several lines, runs on sonnet.")
        self.assertError("plugin.model-mention")

    def test_model_named_in_skill_or_manifest(self):
        for rel, old in (("plugins/orchestration/skills/roadmap-tracker/SKILL.md", "# Body"),
                         ("plugins/orchestration/.claude-plugin/plugin.json", '"orchestration"')):
            with self.subTest(rel=rel):
                fx = Fixture()
                self.addCleanup(fx.cleanup)
                new = "# Body haiku" if rel.endswith(".md") else '"orchestration", "description": "Haiku"'
                fx.replace(rel, old, new)
                report = validate.validate(fx.root)
                self.assertIn("plugin.model-mention", report.codes(validate.ERROR))

    def test_model_word_inside_other_word_ok(self):
        self.fx.replace(self.AGENT_PATH, "Body.", "Body: magnum opuscule.")
        self.assertEqual(self.run_validate().findings, [])

    def test_bad_effort(self):
        self.fx.replace(self.AGENT_PATH, "effort: high", "effort: extreme")
        self.assertError("frontmatter.effort")

    def test_mascot_known_ok_unknown_warns(self):
        self.fx.replace(self.AGENT_PATH, "effort: high", "effort: high\nmascot: chef")
        self.assertEqual(self.run_validate().findings, [])
        self.fx.replace(self.AGENT_PATH, "mascot: chef", "mascot: unicorn")
        self.assertWarning("frontmatter.mascot")

    def test_plugin_agent_ignored_fields_warn(self):
        for key in ("hooks", "mcpServers", "permissionMode"):
            with self.subTest(key=key):
                self.fx.write(self.AGENT_PATH, dedent(AGENT).replace("effort: high", f"{key}:\n  - x"))
                self.assertWarning("frontmatter.plugin-agent-ignored")

    def test_launch_line_list_option_without_separator(self):
        for body in ('`claude --bg --model <m> --disallowedTools "Bash(claude *)" "<task brief>"`',
                     '`claude --background --add-dir=../x "<brief>"`',
                     '```bash\nclaude --bg -n t1 --allowedTools Read Grep "<brief>"\n```'):
            with self.subTest(body=body):
                self.fx.replace(self.AGENT_PATH, "Body.", f"Body.\n\n{body}\n")
                self.assertError("plugin.launch-separator")
                self.fx.write(self.AGENT_PATH, dedent(AGENT))

    def test_launch_line_separator_ok(self):
        for body in ('`claude --bg --disallowedTools "Bash(claude *)" -- "<task brief>"`',
                     '`claude --bg --model <m> "<task brief>"`',
                     '`claude -p --disallowedTools Bash "<brief>"`',
                     'add `--disallowedTools "Bash(claude *)"` to the line'):
            with self.subTest(body=body):
                self.fx.replace(self.AGENT_PATH, "Body.", f"Body.\n\n{body}\n")
                self.assertEqual(self.run_validate().findings, [])
                self.fx.write(self.AGENT_PATH, dedent(AGENT))

    def test_ignored_fields_ok_in_skill(self):
        self.fx.replace(self.SKILL_PATH, "description: Maintain the roadmap.", "description: x\nhooks: {}")
        self.assertEqual(self.run_validate().findings, [])


class TestCanon(Base):
    def test_duplicate_id_across_files(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- `CANON:13` [MODEL 2026-09-01] Duplicate.\n")
        self.assertError("canon.duplicate-id")

    def test_duplicate_id_with_deprecated_entry(self):
        # A struck ID is never reused.
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- `CANON:9` [MODEL 2026-09-01] Reuses a deprecated ID.\n")
        self.assertError("canon.duplicate-id")

    def test_missing_provenance(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- `CANON:30` No provenance.\n")
        self.assertError("canon.entry")

    def test_user_without_name(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- `CANON:30` [USER 2026-09-01] No name.\n")
        self.assertError("canon.entry")

    def test_missing_date(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- `CANON:30` [MODEL] No date.\n")
        self.assertError("canon.entry")

    def test_invalid_date(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- `CANON:30` [MODEL 2026-13-40] Impossible date.\n")
        self.assertError("canon.date")

    def test_id_without_backticks(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- CANON:30 [MODEL 2026-09-01] No backticks.\n")
        self.assertError("canon.entry")

    def test_floating_prose(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n", "# Expectations\n\nA free paragraph.\n")
        self.assertError("canon.prose")

    def test_missing_title(self):
        self.fx.write(".claude/canon/expectations.md", "- `CANON:30` [MODEL 2026-09-01] No title.\n")
        self.assertError("canon.title")

    def test_strike_without_obsolete(self):
        self.fx.replace(".claude/canon/tests.md",
                        "  — obsolete 2026-08-14: `make test` was removed, replaced by `CANON:12`.\n", "")
        self.assertError("canon.obsolete-missing")

    def test_obsolete_without_strike(self):
        self.fx.replace(".claude/canon/invariants.md",
                        "- `CANON:1` [USER:pazimor 2026-09-01] No dependency on a third-party service.",
                        "- `CANON:1` [USER:pazimor 2026-09-01] No dependency. — obsolete 2026-09-02: reason")
        self.assertError("canon.obsolete-unstruck")

    def test_unclosed_strike(self):
        self.fx.replace(".claude/canon/tests.md", "via `make test`.~~", "via `make test`.")
        self.assertError("canon.strike")

    def test_obsolete_without_reason(self):
        self.fx.replace(".claude/canon/tests.md",
                        "— obsolete 2026-08-14: `make test` was removed, replaced by `CANON:12`.",
                        "— obsolete 2026-08-14")
        self.assertError("canon.obsolete-missing")

    def test_promoted_model_entry(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- `CANON:30` [MODEL 2026-09-01] Point. (promoted from MODEL)\n")
        self.assertError("canon.promotion")

    def test_misc_forbidden(self):
        self.fx.write(".claude/canon/misc.md", "# Misc\n")
        self.assertError("canon.misc")

    def test_unknown_reference_warns(self):
        self.fx.replace(".claude/canon/expectations.md", "# Expectations\n",
                        "# Expectations\n\n- `CANON:30` [MODEL 2026-09-01] See `CANON:99`.\n")
        self.assertWarning("canon.unknown-ref")

    def test_real_repo_deprecated_form(self):
        # Exact form of `.claude/canon/invariants.md` (long struck entry + obsolete line below).
        self.fx.write(".claude/canon/expectations.md", dedent("""\
            # Expectations

            - ~~`CANON:6` [USER:pazimor 2026-09-01] Nothing from the legacy (market-mem, plugin memory) is dismantled before validation (ROADMAP:TASK:8).~~
              — obsolete 2026-09-24: user decision; replaced by `CANON:7`.
            - ~~`CANON:7` [USER:pazimor 2026-09-24] The plugin memory is removed.~~
              — obsolete 2026-09-24: the explicit decision has come, replaced by `CANON:1`.
            """))
        self.assertEqual(self.run_validate().findings, [])


class TestRoadmap(Base):
    RM = ".claude/roadmap.md"

    def test_duplicate_task_id(self):
        self.fx.replace(self.RM, "`ROADMAP:TASK:6`", "`ROADMAP:TASK:5`")
        self.assertError("roadmap.duplicate-id")

    def test_duplicate_spec_id(self):
        self.fx.replace(self.RM, "Rules:", "- `ROADMAP:SPEC:1` **Duplicate** [draft]\n  - Canon: x\n\nRules:")
        self.assertError("roadmap.duplicate-id")

    def test_duplicate_milestone_id(self):
        self.fx.replace(self.RM, "(`ROADMAP:MILESTONE:2`, active)", "(`ROADMAP:MILESTONE:1`, active)")
        self.assertError("roadmap.duplicate-id")

    def test_same_number_different_families_ok(self):
        # IDs are unique PER type: SPEC:1, MILESTONE:1 and TASK:1 coexist (already the case in the fixture).
        self.assertEqual(self.run_validate().errors, [])

    def test_unknown_dependency(self):
        self.fx.replace(self.RM, "depends on ROADMAP:TASK:3", "depends on ROADMAP:TASK:42")
        self.assertError("roadmap.unknown-ref")

    def test_unknown_spec(self):
        self.fx.replace(self.RM, "Title _(implements ROADMAP:SPEC:1)_", "Title _(implements ROADMAP:SPEC:7)_")
        self.assertError("roadmap.unknown-ref")

    def test_wrong_family_in_depends(self):
        self.fx.replace(self.RM, "depends on ROADMAP:TASK:3", "depends on ROADMAP:SPEC:1")
        self.assertError("roadmap.suffix-id")

    def test_short_id_rejected(self):
        self.fx.replace(self.RM, "depends on ROADMAP:TASK:3", "depends on TASK:3")
        self.assertError("roadmap.suffix-id")

    def test_in_progress_without_claim(self):
        self.fx.replace(self.RM, "; claimed by pazimor", "")
        self.assertError("roadmap.claim-missing")

    def test_in_progress_blocked_without_claim_ok(self):
        # TASK:4 of the fixture: [~] with `blocked:` alone, accepted (reading of the brief, see docs/grammar.md).
        self.assertEqual(self.run_validate().errors, [])

    def test_done_with_claim(self):
        self.fx.replace(self.RM, "Title _(implements ROADMAP:SPEC:1)_",
                        "Title _(implements ROADMAP:SPEC:1; claimed by pazimor)_")
        self.assertError("roadmap.claim-on-done")

    def test_suffix_order(self):
        self.fx.replace(self.RM, "_(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:1)_",
                        "_(depends on ROADMAP:TASK:1; implements ROADMAP:SPEC:1)_")
        self.assertError("roadmap.suffix-order")

    def test_unknown_suffix_element(self):
        self.fx.replace(self.RM, "_(depends on ROADMAP:TASK:3)_", "_(needs ROADMAP:TASK:3)_")
        self.assertError("roadmap.suffix")

    def test_bad_checkbox(self):
        self.fx.replace(self.RM, "- [ ] `ROADMAP:TASK:5`", "- [X] `ROADMAP:TASK:5`")
        self.assertError("roadmap.checkbox")

    def test_bad_milestone_header(self):
        self.fx.replace(self.RM, "(`ROADMAP:MILESTONE:2`, active)", "(`ROADMAP:MILESTONE:2`, ongoing)")
        self.assertError("roadmap.milestone")

    def test_bad_spec_status(self):
        self.fx.replace(self.RM, "**Spec title** [active]", "**Spec title** [wip]")
        self.assertError("roadmap.spec")

    def test_unknown_section(self):
        self.fx.replace(self.RM, "## Backlog (no milestone)", "## Ideas")
        self.assertError("roadmap.section")

    def test_missing_title(self):
        self.fx.replace(self.RM, "# Roadmap\n", "# Plan\n")
        self.assertError("roadmap.title")

    def test_milestone_done_with_open_task(self):
        self.fx.replace(self.RM, "- [x] `ROADMAP:TASK:2`", "- [ ] `ROADMAP:TASK:2`")
        self.assertError("roadmap.milestone-done")

    def test_dependency_cycle(self):
        self.fx.replace(self.RM, "Title _(implements ROADMAP:SPEC:1)_",
                        "Title _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:2)_")
        self.assertError("roadmap.dependency-cycle")

    def test_self_dependency(self):
        self.fx.replace(self.RM, "_(depends on ROADMAP:TASK:3)_", "_(depends on ROADMAP:TASK:5)_")
        self.assertError("roadmap.self-dependency")

    def test_done_task_with_undone_dependency_warns(self):
        self.fx.replace(self.RM, "- [ ] `ROADMAP:TASK:5` Title _(depends on ROADMAP:TASK:3)_",
                        "- [x] `ROADMAP:TASK:5` Title _(depends on ROADMAP:TASK:3)_")
        self.assertWarning("roadmap.dependency-not-done")

    def test_unknown_title_prefix_warns(self):
        self.fx.replace(self.RM, "[RESEARCH] Idea", "[IDEA] Idea")
        self.assertWarning("roadmap.title-prefix")

    def test_milestone_without_dod_warns(self):
        self.fx.replace(self.RM, "Milestone DoD: other criterion.\n", "")
        self.assertWarning("roadmap.milestone-dod")

    def test_bullet_before_rules(self):
        self.fx.replace(self.RM, "\nRules:\n", "\n- a rule without a header\n\nRules:\n")
        self.assertError("roadmap.spec")

    def test_unknown_canon_ref_warns(self):
        self.fx.replace(self.RM, "[RESEARCH] Idea", "[RESEARCH] Idea (cf. CANON:77)")
        self.assertWarning("roadmap.unknown-canon-ref")


class TestRepository(unittest.TestCase):
    def test_repository_validates(self):
        # The repo itself: no errors (warnings are tolerated).
        root = Path(__file__).resolve().parents[2]
        report = validate.validate(root)
        self.assertEqual(report.errors, [], "\n".join(map(str, report.errors)))


# ---------------------------------------------------------------------------------------------
# Layout v2: a `.claude/journal/` folder switches the canon and roadmap checks.
# ---------------------------------------------------------------------------------------------

V2_PAGE = """\
    # Tests

    ## Suite

    - `CANON:20` [USER:pazimor] The suite runs from the repo root. Sources: `CANON:12`.
    - `CANON:21` [MODEL] `pytest -q` takes about 40 s. Sources : `CANON:12`, `CANON:13`.

    ### Network

    - `CANON:22` [USER:Alex Q] A test that touches the network is rejected, see `CANON:20`. Sources: `CANON:13`.
    """

V2_JOURNAL = """\
    # Canon journal 2026-10

    - `CANON:12` [USER:pazimor 2026-10-02] Run the suite from the repo root.
    - `CANON:13` [USER:pazimor 2026-10-03] The network is off in tests. (promoted from MODEL)
    - ~~`CANON:9` [MODEL 2026-07-02] The tests run via `make test`.~~
      — obsolete 2026-08-14: replaced by `CANON:12`.
    """

V2_ROADMAP = """\
    # Roadmap

    ## Specs

    - `ROADMAP:SPEC:1` **Spec title** [active]
      - Canon: the settled design.

    Rules:
    - rule 1

    ## M2 — Second (`ROADMAP:MILESTONE:2`, active)

    Milestone DoD: other criterion.

    - [~] `ROADMAP:TASK:3` Title _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:1; claimed by pazimor; history: roadmap-2026-10.md)_
    - [~] `ROADMAP:TASK:4` Title _(blocked: waiting for an answer; with a semicolon; history: roadmap-2026-10.md)_
    - [ ] `ROADMAP:TASK:5` Title _(depends on ROADMAP:TASK:3)_

    ## Backlog (no milestone)

    - [ ] `ROADMAP:TASK:6` [RESEARCH] Idea (cf. CANON:20)
    """

V2_ARCHIVE = """\
    # Roadmap archive 2026-10

    ## M1 — First (`ROADMAP:MILESTONE:1`, done)

    - `ROADMAP:SPEC:7` **Old spec** [retired]

    - [x] `ROADMAP:TASK:1` Closed title _(implements ROADMAP:SPEC:7)_
    - [x] `ROADMAP:TASK:2` Closed title
      - [x] `ROADMAP:TASK:77` indented line, ignored
    - [ ] `ROADMAP:TASK:3` history line of an open task
    - [~] `ROADMAP:TASK:3` second history line, same ID
    """


class FixtureV2(Fixture):
    """A conforming v2 project: pages with Sources, canon journal, roadmap, roadmap archive."""

    def __init__(self):
        super().__init__()
        shutil.rmtree(self.root / ".claude" / "canon")
        self.write(".claude/canon/tests.md", dedent(V2_PAGE))
        self.write(".claude/journal/canon-2026-10.md", dedent(V2_JOURNAL))
        self.write(".claude/journal/roadmap-2026-10.md", dedent(V2_ARCHIVE))
        self.write(".claude/roadmap.md", dedent(V2_ROADMAP))


class BaseV2(Base):
    PAGE = ".claude/canon/tests.md"
    JOURNAL = ".claude/journal/canon-2026-10.md"
    ARCHIVE = ".claude/journal/roadmap-2026-10.md"
    RM = ".claude/roadmap.md"

    def setUp(self):
        self.fx = FixtureV2()
        self.addCleanup(self.fx.cleanup)

    def assertNoError(self):
        report = self.run_validate()
        self.assertEqual(report.errors, [], "\n".join(map(str, report.errors)))
        return report


class TestV2Valid(BaseV2):
    def test_conforming_project_has_no_findings(self):
        report = self.run_validate()
        self.assertEqual(report.findings, [], "\n".join(map(str, report.findings)))

    def test_sources_with_space_before_colon(self):
        # CANON:21 of the fixture already uses `Sources :`; the dotted form passes too.
        self.assertIn("Sources :", self.fx.read(self.PAGE))
        self.assertEqual(self.run_validate().findings, [])

    def test_sources_without_final_dot_and_trailing_spaces(self):
        self.fx.replace(self.PAGE, "`CANON:12`.\n", "`CANON:12`   \n")
        self.assertEqual(self.run_validate().findings, [])

    def test_main_exit_code(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(validate.main([str(self.fx.root)]), 0)
            self.fx.replace(self.PAGE, "Sources: `CANON:12`.", "")
            self.assertEqual(validate.main([str(self.fx.root)]), 1)

    def test_journal_folder_without_files_is_v2(self):
        # The folder alone switches the layout: a v1 entry on a page is no longer valid.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".claude" / "journal").mkdir(parents=True)
            (root / ".claude" / "canon").mkdir(parents=True)
            (root / ".claude" / "canon" / "tests.md").write_text(
                "# Tests\n\n- `CANON:1` [MODEL 2026-09-01] v1 entry.\n", encoding="utf-8")
            self.assertIn("canon.page-rule", validate.validate(root).codes(validate.ERROR))

    def test_other_files_of_the_journal_are_ignored(self):
        notes = ("# Notes\n\n```\n- `CANON:12` [MODEL 2026-01-01] copy\n- [x] `ROADMAP:TASK:1` closed again\n"
                 "- [ ] `ROADMAP:TASK:999` history of nothing\n```\n\n`CANON:20` stray\n")
        for name in ("notes-2026-11.md", "canon-2026-1.md", "roadmap-archive.md", "canon-2026-10.md.bak"):
            with self.subTest(name=name):
                self.fx.write(f".claude/journal/{name}", notes)
                self.assertEqual(self.run_validate().findings, [])


class TestV2CanonPages(BaseV2):
    def test_title_required(self):
        self.fx.replace(self.PAGE, "# Tests\n", "Tests\n")
        self.assertError("canon.title")

    def test_prose_forbidden(self):
        self.fx.replace(self.PAGE, "## Suite\n", "## Suite\n\nA free paragraph.\n")
        self.assertError("canon.prose")

    def test_headings_of_any_text_and_blank_lines_ok(self):
        self.fx.replace(self.PAGE, "## Suite", "## Une suite — n'importe quel titre !")
        self.assertEqual(self.run_validate().findings, [])

    def test_continuation_line_rejected(self):
        self.fx.replace(self.PAGE, "from the repo root. Sources: `CANON:12`.",
                        "from the repo root.\n      Sources: `CANON:12`.")
        self.assertError("canon.page-rule")

    def test_dated_user_provenance_rejected(self):
        self.fx.replace(self.PAGE, "[USER:pazimor]", "[USER:pazimor 2026-11-04]")
        report = self.assertError("canon.page-rule")
        self.assertNotIn("canon.page-sources", report.codes())

    def test_dated_model_provenance_rejected(self):
        self.fx.replace(self.PAGE, "[MODEL]", "[MODEL 2026-11-04]")
        self.assertError("canon.page-rule")

    def test_missing_backticks_rejected(self):
        self.fx.replace(self.PAGE, "`CANON:20` [USER", "CANON:20 [USER")
        self.assertError("canon.page-rule")

    def test_empty_text_rejected(self):
        self.fx.replace(self.PAGE, "The suite runs from the repo root. Sources", "Sources")
        self.assertError("canon.page-rule")

    def test_missing_sources_tail(self):
        self.fx.replace(self.PAGE, " Sources: `CANON:12`.", "")
        self.assertError("canon.page-sources")

    def test_malformed_sources_tails(self):
        for tail in ("Sources: CANON:12.", "Sources: `CANON:12` `CANON:13`.", "Sources:", "Sources: `CANON:12`, ",
                     "Sources: `CANON:12`; `CANON:13`.", "Sources: `CANON:12`. Later."):
            with self.subTest(tail=tail):
                self.fx.write(self.PAGE, dedent(V2_PAGE).replace("Sources: `CANON:12`.", tail, 1))
                self.assertError("canon.page-sources")

    def test_strike_forbidden(self):
        self.fx.replace(self.PAGE, "The suite runs", "~~The suite~~ runs")
        self.assertError("canon.page-strike")

    def test_obsolete_marker_forbidden(self):
        for mark in ("— obsolete 2026-08-14: gone", "— obsolète 2026-08-14 : parti"):
            with self.subTest(mark=mark):
                self.fx.write(self.PAGE, dedent(V2_PAGE).replace("takes about 40 s.", f"takes 40 s. {mark}"))
                self.assertError("canon.page-strike")

    def test_misc_page(self):
        self.fx.write(".claude/canon/misc.md", "# Misc\n")
        self.assertError("canon.misc")

    def test_page_over_budget_warns_only(self):
        self.fx.write(self.PAGE, dedent(V2_PAGE) + "".join(
            f"- `CANON:{1000 + i}` [MODEL] {'x' * 120} Sources: `CANON:12`.\n" for i in range(400)))
        self.assertGreater(len((self.fx.root / self.PAGE).read_bytes()), validate.PAGE_BUDGET)
        report = self.assertWarning("canon.page-size")
        self.assertEqual(report.codes(validate.ERROR), [])

    def test_unknown_ref_in_rule_text_warns(self):
        self.fx.replace(self.PAGE, "see `CANON:20`", "see `CANON:777`")
        self.assertWarning("canon.unknown-ref")

    def test_source_must_exist(self):
        self.fx.replace(self.PAGE, "Sources: `CANON:12`.", "Sources: `CANON:777`.")
        self.assertError("canon.unknown-source")

    def test_source_must_be_a_journal_entry_not_a_page_rule(self):
        self.fx.replace(self.PAGE, "Sources: `CANON:12`.", "Sources: `CANON:21`.")
        report = self.assertError("canon.unknown-source")
        self.assertIn("only a page rule", "\n".join(map(str, report.findings)))


class TestV2Ids(BaseV2):
    def test_duplicate_between_two_pages(self):
        self.fx.write(".claude/canon/conventions.md", "# Conventions\n\n- `CANON:20` [MODEL] Again. Sources: `CANON:12`.\n")
        self.assertError("canon.duplicate-id")

    def test_duplicate_between_page_and_journal(self):
        self.fx.replace(self.PAGE, "`CANON:21` [MODEL]", "`CANON:13` [MODEL]")
        self.assertError("canon.duplicate-id")

    def test_duplicate_inside_a_journal_file(self):
        self.fx.replace(self.JOURNAL, "`CANON:13` [USER:pazimor 2026-10-03]", "`CANON:12` [MODEL 2026-10-03]")
        self.assertError("canon.duplicate-id")

    def test_duplicate_across_journal_months(self):
        self.fx.write(".claude/journal/canon-2026-11.md", "# Canon journal 2026-11\n\n- `CANON:12` [MODEL 2026-11-01] Again.\n")
        self.assertError("canon.duplicate-id")

    def test_source_in_another_month_ok(self):
        self.fx.write(".claude/journal/canon-2026-11.md", "# Canon journal 2026-11\n\n- `CANON:30` [MODEL 2026-11-01] New.\n")
        self.fx.replace(self.PAGE, "Sources: `CANON:12`.", "Sources: `CANON:30`.")
        self.assertEqual(self.run_validate().findings, [])


class TestV2Journal(BaseV2):
    def test_legacy_content_is_tolerated(self):
        self.fx.write(self.JOURNAL, dedent("""\
            # Journal

            ## Un titre libre
            - ~~`CANON:9` [MODEL 2026-07-02] Struck, French marker.~~ — obsolète 2026-08-14 : remplacée par `CANON:12`.
            - ~~`CANON:10` [MODEL 2026-07-02] Struck, no obsolete marker at all.~~
            `CANON:604` [MODEL 2026-10-05] Entry without the leading dash.
            - ~~`CANON:11` [USER:pazimor 2026-07-02] Whole entry struck.~~
              — obsolete 2026-08-14: replaced by `CANON:12`.
            - `CANON:12` [USER:pazimor 2026-10-02] Run the suite from the repo root.
            - `CANON:13` [MODEL 2026-10-03] Another.
            """))
        report = self.run_validate()
        self.assertEqual(report.errors, [], "\n".join(map(str, report.errors)))
        entry = [f for f in report.warnings if f.code == "journal.entry"]
        self.assertTrue(entry)
        self.assertTrue(all("v1 check `canon." in f.message for f in entry))

    def test_malformed_entry_is_a_warning(self):
        self.fx.write(self.JOURNAL, dedent("""\
            # Journal

            - `CANON:12` [USER:pazimor 2026-13-45] Impossible date.
            - `CANON:13` [OTHER 2026-10-03] Bad provenance.
            """))
        report = self.assertWarning("journal.entry")
        self.assertNotIn("canon.entry", report.codes())

    def test_missing_title_warns(self):
        self.fx.replace(self.JOURNAL, "# Canon journal 2026-10\n", "Canon journal\n")
        self.assertWarning("journal.title")

    def test_unrecognised_line_warns(self):
        self.fx.replace(self.JOURNAL, "- `CANON:13`", "Stray paragraph.\n- `CANON:13`")
        self.assertWarning("journal.prose")

    def test_fenced_blocks_are_never_entries(self):
        self.fx.write(self.JOURNAL, dedent(V2_JOURNAL) + dedent("""\

            ```
            - `CANON:12` [MODEL 2026-10-03] A copy, inside a fence.
            some prose
            ```

            ````md
            ```
            - `CANON:13` [MODEL 2026-10-03] Nested fence.
            ```
            - `CANON:9` [MODEL 2026-10-03] Still inside the outer fence.
            ````
            """))
        self.assertEqual(self.run_validate().findings, [])

    def test_unknown_ref_in_journal_warns(self):
        self.fx.replace(self.JOURNAL, "Run the suite", "Run (see `CANON:888`) the suite")
        self.assertWarning("canon.unknown-ref")

    def test_continuation_lines_join_the_entry(self):
        self.fx.replace(self.JOURNAL, "Run the suite from the repo root.",
                        "Run the suite\n      from the repo root, on two lines.")
        self.assertEqual(self.run_validate().findings, [])


class TestV2Roadmap(BaseV2):
    def test_v1_checks_still_apply(self):
        self.fx.replace(self.RM, "# Roadmap\n", "# Plan\n")
        self.assertError("roadmap.title")

    def test_done_task_rejected(self):
        self.fx.replace(self.RM, "- [ ] `ROADMAP:TASK:6`", "- [x] `ROADMAP:TASK:6`")
        self.assertError("roadmap.done-task")

    def test_history_element_valid_and_last(self):
        self.assertEqual(self.run_validate().findings, [])

    def test_history_bad_name(self):
        for name in ("notes.md", "roadmap-2026.md", "../roadmap-2026-10.md", "roadmap-2026-10.txt"):
            with self.subTest(name=name):
                self.fx.write(self.RM, dedent(V2_ROADMAP).replace("history: roadmap-2026-10.md)_", f"history: {name})_", 1))
                self.assertError("roadmap.history")

    def test_history_file_must_exist(self):
        self.fx.replace(self.RM, "history: roadmap-2026-10.md)_", "history: roadmap-2026-09.md)_")
        self.assertError("roadmap.history")

    def test_history_must_come_last(self):
        self.fx.replace(self.RM, "depends on ROADMAP:TASK:1; claimed by pazimor; history: roadmap-2026-10.md)_",
                        "history: roadmap-2026-10.md; depends on ROADMAP:TASK:1; claimed by pazimor)_")
        self.assertError("roadmap.suffix-order")

    def test_history_after_blocked_does_not_leak_into_blocked(self):
        self.assertNoError()
        self.fx.replace(self.RM, "with a semicolon; history: roadmap-2026-10.md)_",
                        "with a semicolon; history: roadmap-2026-09.md)_")
        self.assertError("roadmap.history")

    def test_history_without_value(self):
        self.fx.replace(self.RM, "claimed by pazimor; history: roadmap-2026-10.md)_", "claimed by pazimor; history:)_")
        self.assertError("roadmap.suffix")

    def test_history_repeated(self):
        self.fx.replace(self.RM, "claimed by pazimor; history: roadmap-2026-10.md)_",
                        "claimed by pazimor; history: roadmap-2026-10.md; history: roadmap-2026-10.md)_")
        self.assertError("roadmap.suffix")

    def test_done_milestone_and_retired_spec_warn(self):
        self.fx.replace(self.RM, "(`ROADMAP:MILESTONE:2`, active)", "(`ROADMAP:MILESTONE:2`, done)")
        self.fx.replace(self.RM, "**Spec title** [active]", "**Spec title** [retired]")
        report = self.run_validate()
        self.assertIn("roadmap.done-milestone", report.codes(validate.WARNING))
        self.assertIn("roadmap.retired-spec", report.codes(validate.WARNING))

    def test_retired_spec_alone_is_only_a_warning(self):
        self.fx.replace(self.RM, "**Spec title** [active]", "**Spec title** [retired]")
        self.assertWarning("roadmap.retired-spec")

    def test_dependency_closed_in_the_archive_is_known_and_done(self):
        # TASK:3 depends on TASK:1, which only exists, closed, in the archive: no unknown-ref, no warning.
        report = self.run_validate()
        self.assertEqual(report.findings, [], "\n".join(map(str, report.findings)))

    def test_dependency_nowhere_is_unknown(self):
        self.fx.replace(self.RM, "depends on ROADMAP:TASK:1;", "depends on ROADMAP:TASK:99;")
        self.assertError("roadmap.unknown-ref")

    def test_spec_closed_in_the_archive_is_known(self):
        self.fx.replace(self.RM, "implements ROADMAP:SPEC:1; depends", "implements ROADMAP:SPEC:7; depends")
        self.assertEqual(self.run_validate().findings, [])
        self.fx.replace(self.RM, "implements ROADMAP:SPEC:7;", "implements ROADMAP:SPEC:8;")
        self.assertError("roadmap.unknown-ref")

    def test_canon_refs_resolve_against_pages_and_journal(self):
        self.fx.replace(self.RM, "cf. CANON:20", "cf. CANON:12, CANON:20, CANON:9")
        self.assertEqual(self.run_validate().findings, [])
        self.fx.replace(self.RM, "CANON:9)", "CANON:555)")
        self.assertWarning("roadmap.unknown-canon-ref")

    def test_roadmap_still_checks_open_dependency_state(self):
        self.fx.replace(self.RM, "- [ ] `ROADMAP:TASK:5` Title _(depends on ROADMAP:TASK:3)_",
                        "- [~] `ROADMAP:TASK:5` Title _(depends on ROADMAP:TASK:6; claimed by x)_")
        self.assertWarning("roadmap.dependency-not-done")


class TestV2Archive(BaseV2):
    def test_closed_and_open(self):
        self.fx.replace(self.ARCHIVE, "- [x] `ROADMAP:TASK:2` Closed title", "- [x] `ROADMAP:TASK:5` Closed title")
        self.assertError("roadmap.closed-and-open")

    def test_closed_twice_in_one_file(self):
        self.fx.replace(self.ARCHIVE, "- [x] `ROADMAP:TASK:2` Closed title", "- [x] `ROADMAP:TASK:1` Closed title")
        self.assertError("roadmap.closed-twice")

    def test_closed_twice_across_files(self):
        self.fx.write(".claude/journal/roadmap-2026-11.md", "# Archive\n\n- [x] `ROADMAP:TASK:1` Again\n")
        self.assertError("roadmap.closed-twice")

    def test_history_line_of_a_closed_task(self):
        self.fx.replace(self.ARCHIVE, "- [ ] `ROADMAP:TASK:3` history line", "- [ ] `ROADMAP:TASK:2` history line")
        self.assertError("roadmap.history-not-open")

    def test_history_line_of_an_absent_task(self):
        self.fx.replace(self.ARCHIVE, "- [ ] `ROADMAP:TASK:3` history line", "- [ ] `ROADMAP:TASK:404` history line")
        self.assertError("roadmap.history-not-open")

    def test_history_lines_may_repeat(self):
        self.assertEqual(self.run_validate().findings, [])
        self.fx.write(self.ARCHIVE, dedent(V2_ARCHIVE) + "- [ ] `ROADMAP:TASK:3` third\n")
        self.assertEqual(self.run_validate().findings, [])

    def test_free_prose_and_titles_in_any_language_tolerated(self):
        self.fx.write(self.ARCHIVE, dedent(V2_ARCHIVE) + dedent("""\

            ## Jalon 4 — Terminé (`ROADMAP:MILESTONE:4`, terminé)

            Du texte libre, des décisions datées.

            Rules:
            - une règle

            - `ROADMAP:SPEC:12` **Spec** [obsolète]
              - Canon: texte
            """))
        self.assertEqual(self.run_validate().findings, [])

    def test_fenced_lines_of_the_archive_ignored(self):
        self.fx.write(self.ARCHIVE, dedent(V2_ARCHIVE) + "\n```\n- [x] `ROADMAP:TASK:1` copy\n- [ ] `ROADMAP:TASK:404` x\n```\n")
        self.assertEqual(self.run_validate().findings, [])

    def test_other_checkboxes_ignored(self):
        self.fx.write(self.ARCHIVE, dedent(V2_ARCHIVE) + "- [X] `ROADMAP:TASK:5` odd box\n- [?] `ROADMAP:TASK:404` odd\n")
        self.assertEqual(self.run_validate().findings, [])

    def test_no_roadmap_skips_cross_checks_but_not_closed_twice(self):
        (self.fx.root / self.RM).unlink()
        self.assertEqual(self.run_validate().findings, [])
        self.fx.write(".claude/journal/roadmap-2026-11.md", "- [x] `ROADMAP:TASK:1` Again\n")
        self.assertError("roadmap.closed-twice")


class TestV1Unchanged(Base):
    def test_history_suffix_is_an_unknown_element_in_v1(self):
        self.fx.replace(".claude/roadmap.md", "_(depends on ROADMAP:TASK:3)_",
                        "_(depends on ROADMAP:TASK:3; history: roadmap-2026-10.md)_")
        report = self.assertError("roadmap.suffix")
        text = "\n".join(map(str, report.findings))
        self.assertIn("(expected implements / depends on / claimed by / blocked:)", text)

    def test_closed_task_and_done_milestone_are_fine_in_v1(self):
        report = self.run_validate()
        self.assertEqual(report.findings, [])
        self.assertIn("[x]", self.fx.read(".claude/roadmap.md"))

    def test_journal_files_are_not_read_without_the_folder(self):
        # A v1 project: canon files carry dated entries, no `.claude/journal/` anywhere.
        self.assertFalse((self.fx.root / ".claude" / "journal").exists())
        self.assertEqual(self.run_validate().findings, [])


if __name__ == "__main__":
    unittest.main()

"""Validator tests (unittest, stdlib only).

Run from the repo root: python3 -m unittest discover -s scripts/tests -v
"""

import io
import json
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


if __name__ == "__main__":
    unittest.main()

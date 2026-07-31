#!/usr/bin/env python3
"""Tests that the sub-agent prompts, the schema reference, and the consumers agree.

Run from the skill root:

    python -m unittest tests.test_agent_prompt_contracts -v
    python -m tests.test_agent_prompt_contracts

Why this file exists: `agents/*.md` is the only part of the bundle no program
reads. Nothing imports it, nothing validates it, and nothing notices when the
shape it tells a sub-agent to emit stops matching the shape a consumer reads or
`references/schemas.md` documents. That is not a hypothetical - it is R18, and
the drift it should have caught (an assignment key that gained three audit
fields; a schema doc still describing a write path that had been replaced) was
found by a human verifier instead.

The checks are structural on purpose. They compare *key trees* - field names and
nesting, with every leaf value discarded - so a prompt is free to reword its
slots, its guidance, and its examples without failing a test, and is not free to
rename a field, move it, or add one that nothing downstream knows about.

What is covered:

  1. Every ```json block in agents/*.md is valid JSON.
  2. Each agent's documented output block has the same key tree as the block for
     that artifact in references/schemas.md.
  3. The blocks grader.md promises are always present are exactly the ones
     validate_grading requires - probed by removing each and checking it fails.
  4. The de-identification reference implementation in comparator.md is executed,
     and the assignment key it really writes matches the documented one. The
     recorded seed is replayed to confirm it reproduces the A/B mapping.
  5. The eight top-level benchmark.json keys analyzer.md tells the analyst to
     expect are exactly what aggregate_benchmark emits and what schemas.md shows.

What is NOT covered: prose. A sentence in either file can still contradict the
mechanism without failing here. Item 4 is the closest thing to a guard against
that, because it runs the code the prose describes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.validate_grading import validate_grading_file  # noqa: E402

AGENTS = SKILL_ROOT / "agents"
SCHEMAS_MD = SKILL_ROOT / "references" / "schemas.md"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def fenced_blocks(path: Path, language: str) -> list[str]:
    """Every ```<language> block in a markdown file, in order."""
    text = path.read_text(encoding="utf-8")
    return re.findall(rf"```{language}\n(.*?)```", text, re.S)


def json_blocks(path: Path) -> list:
    """Every ```json block in a markdown file, parsed."""
    return [json.loads(b) for b in fenced_blocks(path, "json")]


def find_block(blocks, *required_keys):
    """The first parsed block that is an object carrying all of `required_keys`."""
    for block in blocks:
        if isinstance(block, dict) and all(k in block for k in required_keys):
            return block
    return None


def key_tree(obj):
    """Field names and nesting only; every leaf value discarded.

    Lists collapse to their first element, so a one-entry example and a
    three-entry one compare equal as long as the entries have the same shape.
    """
    if isinstance(obj, dict):
        return {k: key_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [key_tree(v) for v in obj[:1]]
    return None


def shape_mismatch(a, b, path="") -> str | None:
    """First structural disagreement between two key trees, or None.

    An empty array matches an array of anything. `"needs_review": []` and
    `"needs_review": ["{Item_It_Flagged_For_A_Human}"]` are the same schema -
    one example happens to show the empty case, and a test that called that a
    contract violation would be noise that trains people to ignore it.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            where = f"{path}.{key}" if path else key
            if key not in a:
                return f"{where}: absent on the left, present on the right"
            if key not in b:
                return f"{where}: present on the left, absent on the right"
            found = shape_mismatch(a[key], b[key], where)
            if found:
                return found
        return None
    if isinstance(a, list) and isinstance(b, list):
        if not a or not b:
            return None
        return shape_mismatch(a[0], b[0], f"{path}[]")
    if isinstance(a, (dict, list)) != isinstance(b, (dict, list)):
        return f"{path or '<root>'}: {type(a).__name__} vs {type(b).__name__}"
    return None


# --------------------------------------------------------------------------
# 1. The prompts' own JSON is JSON
# --------------------------------------------------------------------------

class AgentJsonBlocksTest(unittest.TestCase):
    """A slot-bearing example is still expected to parse."""

    def test_every_json_block_in_every_agent_prompt_parses(self):
        found = 0
        for path in sorted(AGENTS.glob("*.md")):
            for idx, raw in enumerate(fenced_blocks(path, "json"), start=1):
                with self.subTest(prompt=path.name, block=idx):
                    try:
                        json.loads(raw)
                    except json.JSONDecodeError as exc:
                        self.fail(f"{path.name} json block {idx}: {exc}")
                    found += 1
        self.assertGreater(found, 0, "no ```json blocks found under agents/")


# --------------------------------------------------------------------------
# 2. Prompt output shapes == references/schemas.md
# --------------------------------------------------------------------------

class PromptVsSchemaReferenceTest(unittest.TestCase):
    """The shape a sub-agent is told to emit is the shape the doc records."""

    @classmethod
    def setUpClass(cls):
        cls.schemas = json_blocks(SCHEMAS_MD)

    def assert_same_shape(self, agent_file, agent_keys, schema_keys, artifact):
        agent_block = find_block(json_blocks(AGENTS / agent_file), *agent_keys)
        self.assertIsNotNone(
            agent_block, f"no {artifact} block found in agents/{agent_file}")
        doc_block = find_block(self.schemas, *schema_keys)
        self.assertIsNotNone(
            doc_block, f"no {artifact} block found in references/schemas.md")
        found = shape_mismatch(key_tree(agent_block), key_tree(doc_block))
        self.assertIsNone(
            found,
            f"{artifact}: agents/{agent_file} (left) and references/schemas.md "
            f"(right) disagree about field names or nesting -- {found}",
        )

    def test_grading_json(self):
        self.assert_same_shape(
            "grader.md", ("expectations", "summary", "claims"),
            ("expectations", "summary", "claims"), "grading.json")

    def test_comparison_json(self):
        self.assert_same_shape(
            "comparator.md", ("winner", "rubric"),
            ("winner", "rubric"), "comparison.json")

    def test_analysis_json(self):
        self.assert_same_shape(
            "analyzer.md", ("comparison_summary", "improvement_suggestions"),
            ("comparison_summary", "improvement_suggestions"), "analysis.json")


# --------------------------------------------------------------------------
# 3. grader.md's "always present" == validate_grading's "required"
# --------------------------------------------------------------------------

class GraderRequiredBlocksTest(unittest.TestCase):
    """`expectations` and `summary` are required by both, and nothing else is.

    grader.md states that those two are always written and that `claims`,
    `user_notes_summary` and `eval_feedback` may be omitted. The validator has
    to hold the same line: requiring an optional block would make a conforming
    grader fail, and accepting a missing required one is the silent-zero this
    whole pipeline was rebuilt to close.
    """

    ALWAYS_PRESENT = ("expectations", "summary")
    OMITTABLE = ("claims", "user_notes_summary", "eval_feedback")

    @classmethod
    def setUpClass(cls):
        cls.full = find_block(
            json_blocks(AGENTS / "grader.md"), "expectations", "summary", "claims")
        assert cls.full is not None, "grader.md output block not found"

    def _concrete(self):
        """The grader block with its slots replaced by conforming values.

        The prompt's example is a frame - `"passed": "{Boolean...}"` is a string
        - so it cannot be validated as-is. Only the values are substituted; every
        field name and every nesting level comes from the prompt itself.
        """
        block = json.loads(json.dumps(self.full))
        block["expectations"] = [
            {"text": "first", "passed": True, "evidence": "seen"},
            {"text": "second", "passed": False, "evidence": "absent"},
        ]
        block["summary"] = {"passed": 1, "failed": 1, "total": 2, "pass_rate": 0.5}
        for claim in block.get("claims", []):
            claim["verified"] = True
            claim["type"] = "factual"
        return block

    def _errors_for(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "grading.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors, _warnings = validate_grading_file(path)
        return errors

    def test_grader_block_names_the_blocks_the_validator_requires(self):
        self.assertEqual(self._errors_for(self._concrete()), [])

    def test_removing_an_always_present_block_is_an_error(self):
        for field in self.ALWAYS_PRESENT:
            with self.subTest(removed=field):
                payload = self._concrete()
                del payload[field]
                self.assertTrue(
                    self._errors_for(payload),
                    f"validate_grading accepts a grading.json with no "
                    f"'{field}', but grader.md promises it is always written",
                )

    def test_removing_an_omittable_block_is_not_an_error(self):
        for field in self.OMITTABLE:
            with self.subTest(removed=field):
                payload = self._concrete()
                payload.pop(field, None)
                self.assertEqual(
                    self._errors_for(payload), [],
                    f"validate_grading rejects a grading.json with no "
                    f"'{field}', but grader.md says it may be omitted",
                )


# --------------------------------------------------------------------------
# 4. comparator.md's de-identification code really writes the documented key
# --------------------------------------------------------------------------

class DeidentifyReferenceImplementationTest(unittest.TestCase):
    """Execute the reference implementation and check what it actually writes.

    This is the check that would have caught `seed`/`swapped`/`draw` being added
    to the assignment key while references/schemas.md still documented two keys.
    """

    @classmethod
    def setUpClass(cls):
        blocks = [b for b in fenced_blocks(AGENTS / "comparator.md", "python")
                  if "def deidentify" in b]
        assert blocks, "no deidentify() block found in agents/comparator.md"
        namespace: dict = {}
        exec(compile(blocks[0], "comparator.md", "exec"), namespace)  # noqa: S102
        # staticmethod, or attribute access binds it and shifts every argument.
        cls.deidentify = staticmethod(namespace["deidentify"])
        # Located by A/B alone, not by the audit keys - otherwise dropping one
        # from the doc reads as "block not found" instead of naming the drift.
        cls.documented = find_block(json_blocks(SCHEMAS_MD), "A", "B")
        assert cls.documented is not None, \
            "no assignment_key.json block found in references/schemas.md"

    def _run(self, seed=None):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        outputs = {}
        for config in ("with_skill", "without_skill"):
            src = tmp / "src" / config
            src.mkdir(parents=True)
            (src / "result.txt").write_text(config, encoding="utf-8")
            outputs[config] = src
        comparison_dir = tmp / "comparisons" / "eval-0"
        comparison_dir.mkdir(parents=True)
        key = self.deidentify(outputs, comparison_dir, seed=seed)
        on_disk = json.loads(
            (comparison_dir / "assignment_key.json").read_text(encoding="utf-8"))
        return key, on_disk, comparison_dir

    def test_written_key_matches_the_documented_shape(self):
        _key, on_disk, _dir = self._run(seed=12345)
        written, documented = set(on_disk), set(self.documented)
        self.assertEqual(
            written, documented,
            f"assignment_key.json and references/schemas.md disagree: "
            f"written but undocumented {sorted(written - documented)}, "
            f"documented but never written {sorted(documented - written)}",
        )
        for label in ("A", "B"):
            self.assertEqual(
                set(on_disk[label]), set(self.documented[label]),
                f"assignment_key.json['{label}'] and the documented example "
                f"disagree",
            )

    def test_recorded_seed_replays_the_assignment(self):
        """A seed that does not reproduce the mapping is a record of nothing."""
        import random

        key, _on_disk, _dir = self._run()
        configs = sorted(("with_skill", "without_skill"))
        replay = list(configs)
        if random.Random(key["seed"]).random() < 0.5:
            replay.reverse()
        self.assertEqual(
            [key["A"]["configuration"], key["B"]["configuration"]], replay,
            "replaying the recorded seed does not reproduce the A/B mapping; "
            "the assignment was chosen rather than drawn, or `draw` is stale",
        )

    def test_swapped_agrees_with_the_recorded_seed(self):
        import random

        key, _on_disk, _dir = self._run()
        self.assertEqual(
            key["swapped"], random.Random(key["seed"]).random() < 0.5,
            "`swapped` disagrees with what the recorded seed draws",
        )

    def test_candidate_directories_carry_no_provenance(self):
        """The excluded files are the six channels the blinding closes."""
        _key, _on_disk, comparison_dir = self._run(seed=7)
        leaked = [p.name for p in (comparison_dir / "candidates").rglob("*")
                  if p.name in {"transcript.md", "user_notes.md", "metrics.json",
                                "timing.json", "grading.json"}]
        self.assertEqual(leaked, [], f"provenance copied into candidates: {leaked}")

    def test_candidate_directory_names_do_not_name_the_configuration(self):
        _key, on_disk, _dir = self._run(seed=7)
        for label in ("A", "B"):
            name = Path(on_disk[label]["path"]).name
            for config in ("with_skill", "without_skill", "old_skill", "new_skill"):
                self.assertNotIn(
                    config, name,
                    f"candidate {label}'s directory name states the answer",
                )


# --------------------------------------------------------------------------
# 5. analyzer.md's expected benchmark.json keys == what is actually emitted
# --------------------------------------------------------------------------

class AnalyzerBenchmarkKeysTest(unittest.TestCase):
    """analyzer.md names eight top-level keys. Three parties must agree on them."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        root = Path(cls._tmp)
        from tests.make_workspace_fixtures import build
        build(root)
        cls.iteration = root / "canonical" / "iteration-1"
        result = subprocess.run(
            [sys.executable, "-m", "scripts.aggregate_benchmark",
             str(cls.iteration), "--skill-name", "demo"],
            cwd=SKILL_ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        cls.emitted = json.loads(
            (cls.iteration / "benchmark.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _keys_named_in_analyzer(self):
        text = (AGENTS / "analyzer.md").read_text(encoding="utf-8")
        match = re.search(
            r"exactly eight top-level keys\*\*:(.+?)\.\s", text, re.S)
        self.assertIsNotNone(
            match, "analyzer.md no longer states the top-level benchmark keys")
        return set(re.findall(r"`([a-z_]+)`", match.group(1)))

    def test_analyzer_expectation_matches_the_aggregator(self):
        self.assertEqual(
            self._keys_named_in_analyzer(), set(self.emitted),
            "agents/analyzer.md and scripts/aggregate_benchmark.py disagree "
            "about benchmark.json's top-level keys",
        )

    def test_schema_reference_matches_the_aggregator(self):
        documented = find_block(json_blocks(SCHEMAS_MD), "run_summary", "runs")
        self.assertIsNotNone(
            documented, "no benchmark.json block found in references/schemas.md")
        self.assertEqual(
            set(documented), set(self.emitted),
            "references/schemas.md and scripts/aggregate_benchmark.py disagree "
            "about benchmark.json's top-level keys",
        )

    def test_documented_run_result_matches_the_aggregator(self):
        """The field that quietly grew a permanently-null column, twice."""
        documented = find_block(json_blocks(SCHEMAS_MD), "run_summary", "runs")
        self.assertEqual(
            set(documented["runs"][0]["result"]),
            set(self.emitted["runs"][0]["result"]),
            "references/schemas.md and the aggregator disagree about "
            "runs[].result",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

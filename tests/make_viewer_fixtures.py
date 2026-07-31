#!/usr/bin/env python3
"""Build the eval-viewer fixture workspaces.

    python -m tests.make_viewer_fixtures [target-dir]

Default target is tests/fixtures/, which is where the committed copies live.
`tests/test_eval_viewer.py` rebuilds into a temporary directory instead, because
the viewer's server mode writes feedback.json into the workspace it is pointed
at and must never be pointed at the committed copy.

Three workspaces, each aimed at a specific defect class:

  hostile-workspace/       Canonical C1 layout carrying every payload the
                           presentation layer used to mishandle: an output file
                           that closes the embedding <script>, grader evidence
                           that closes an HTML attribute, benchmark.json fields
                           that reach innerHTML, non-ASCII in prompts, outputs
                           and evidence, an expectation with no text, an
                           assertion the two graders worded differently, and one
                           run with no timing.json at all.
  legacy-flat-workspace/   The pre-C1 layout with no run-<K> level. Must still
                           render, and must say out loud that it normalized.
  mixed-eval-id-workspace/ One eval with metadata, one without, one with a null
                           eval_id -- the mix that used to raise TypeError in
                           the run sort and produce no viewer at all. Also the
                           ungraded-run case: no grading.json anywhere in it.
  ordering-swap-workspace/ Two configurations whose graders returned the SAME
                           two assertions in OPPOSITE order, with opposite
                           results. Under positional alignment this renders as
                           two rows on which both configurations agree; the
                           truth is that they disagree on both. Also carries a
                           reworded assertion, so the drift disclosure and the
                           ordering fix are exercised on one page.
  malformed-run-workspace/ A `run-final/` directory: matches the viewer's old
                           `^run-(.+)$` and not the scripts' `^run-(\\d+)$`, so
                           it appeared here and in no benchmark number. Its
                           benchmark.json is the no-primary-survived state:
                           `primary` is null and the survivor stays labelled
                           baseline rather than being promoted.
  mixed-exclusions-        All three exclusion KINDS on one page: a run dropped
  workspace/               entirely, a run that lost only its timing.json, and
                           an eval excluded from the delta but counted in its
                           own configuration's column.
"""

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

# The exclusion reasons below carry the shared contract-C12 condition tag, and
# they are built with the real classifier rather than hand-typed. A fixture
# that spells the tag itself would keep passing after the vocabulary moved,
# which is the whole failure mode C12 exists to close.
from scripts.utils import condition_line  # noqa: E402

DEFAULT_TARGET = Path(__file__).resolve().parent / "fixtures"

# --- payloads ---------------------------------------------------------------
# A skill that emits HTML contains this. It is not an exotic attack; it is a
# Tuesday.
BREAKOUT = '</script><img src=x onerror="window.__EMBED_FIRED=1"><probe id="probe-el"></probe>'
# Grader evidence quotes the output being judged, so a double quote in the
# output reaches a title="..." attribute.
ATTR = 'x" onmouseover="window.__ATTR_FIRED=1" data-z="'
NONASCII = "Итог: 42 — 日本語テキスト — café naïve"


def svg(tag):
    """Markup that announces itself if it ever becomes live DOM."""
    return '<svg onload="window.__X_FIRED_' + tag + '=1"></svg>'


def expectations(texts, passed_flags, evidence_overrides=None):
    out = []
    for i, (text, ok) in enumerate(zip(texts, passed_flags)):
        evidence = (evidence_overrides or {}).get(i, "row %d checked" % i)
        out.append({"text": text, "passed": ok, "evidence": evidence})
    return out


def _stat(mean, stddev, lo, hi, n, missing):
    return {"mean": mean, "stddev": stddev, "min": lo, "max": hi, "n": n, "missing": missing}


def build(target: Path) -> Path:
    target = Path(target)

    def w(rel, text):
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def wj(rel, obj):
        w(rel, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

    # =======================================================================
    # hostile-workspace
    # =======================================================================
    base = "hostile-workspace/iteration-1"
    e0 = base + "/eval-0-emits-html-report"

    wj(e0 + "/eval_metadata.json", {
        "eval_id": 0,
        "eval_name": "emits-html-report",
        # The canonical layout puts this two levels above <config>/run-<K>/.
        "prompt": "Build a one-page HTML report of Q3 sales. " + NONASCII,
        "assertions": ["Output is a CSV file", "Header row present", "Totals row is last"],
    })

    w(e0 + "/with_skill/run-1/outputs/report.html",
      "<h1>Q3 report</h1>\n" + BREAKOUT + "\n<p>done</p>\n")
    w(e0 + "/with_skill/run-1/outputs/notes.md",
      "# Notes\n\n" + NONASCII + "\n\nA line about `</script>` tags in markdown.\n")

    primary_texts = [
        "Output is a CSV file",
        "Header row present",
        "Totals row is last",
        "Currency is formatted",
        "No blank rows",
        "Dates are ISO-8601",
        "Encoding is UTF-8",
        "File is under 1 MB",
        "Column order matches the brief",
        "Footer note is present",
    ]
    # An independent grader on the other configuration reworded the first one.
    # Matching assertions on exact text split this into two half-empty rows.
    baseline_texts = list(primary_texts)
    baseline_texts[0] = "The output is a CSV file"

    e0_primary = expectations(
        primary_texts,
        [True, True, True, True, True, False, False, False, False, False],
        {
            0: "The grader quoted the output: " + ATTR,
            1: "Saw a literal </script> in the emitted markup, which is fine here.",
            2: NONASCII,
        },
    )
    # An expectation the grader forgot to give a text field: it used to render
    # as a bare checkmark indistinguishable from a normal pass.
    e0_primary[9] = {"passed": False, "evidence": "no text field was written for this check"}
    e0_baseline = expectations(
        baseline_texts,
        [True, True, False, False, False, False, False, False, False, False])

    wj(e0 + "/with_skill/run-1/grading.json", {
        "expectations": e0_primary,
        "summary": {"passed": 5, "failed": 5, "total": 10, "pass_rate": 0.5},
    })
    wj(e0 + "/with_skill/run-1/timing.json",
       {"total_tokens": 1200, "duration_ms": 30000, "total_duration_seconds": 30.0})

    w(e0 + "/old_skill/run-1/outputs/report.html", "<h1>Q3 report</h1>\n<p>bare</p>\n")
    wj(e0 + "/old_skill/run-1/grading.json", {
        "expectations": e0_baseline,
        "summary": {"passed": 2, "failed": 8, "total": 10, "pass_rate": 0.2},
    })
    wj(e0 + "/old_skill/run-1/timing.json",
       {"total_tokens": 900, "duration_ms": 45000, "total_duration_seconds": 45.0})

    # eval 1 is small (2 checks vs 10), which is what makes the macro-average
    # 75% while the true pooled rate is 58%.
    e1 = base + "/eval-1-summarises-csv"
    e1_texts = ["Mentions the total", "Two sentences or fewer"]
    e1_primary = expectations(e1_texts, [True, True])
    e1_baseline = expectations(e1_texts, [False, False])

    wj(e1 + "/eval_metadata.json", {
        "eval_id": 1,
        "eval_name": "summarises-csv",
        "prompt": "Summarise sales.csv in two sentences.",
        "assertions": e1_texts,
    })
    w(e1 + "/with_skill/run-1/outputs/summary.txt", "Total sales were 1.2M. " + NONASCII + "\n")
    wj(e1 + "/with_skill/run-1/grading.json", {
        "expectations": e1_primary,
        "summary": {"passed": 2, "failed": 0, "total": 2, "pass_rate": 1.0},
    })
    # NO timing.json for this run. Contract C4: unknown, never 0.

    w(e1 + "/old_skill/run-1/outputs/summary.txt", "Sales happened.\n")
    wj(e1 + "/old_skill/run-1/grading.json", {
        "expectations": e1_baseline,
        "summary": {"passed": 0, "failed": 2, "total": 2, "pass_rate": 0.0},
    })
    wj(e1 + "/old_skill/run-1/timing.json",
       {"total_tokens": 900, "duration_ms": 45000, "total_duration_seconds": 45.0})

    def run(eval_id, eval_name, config, result, exps):
        return {
            "eval_id": eval_id,
            "eval_name": eval_name,
            "configuration": config,
            "run_number": 1,
            "result": result,
            "expectations": exps,
            "notes": [],
        }

    runs = [
        run(0, "emits-html-report " + svg("EVALNAME"), "with_skill",
            {"pass_rate": 0.5, "passed": 5, "failed": 5, "total": 10,
             "time_seconds": 30.0, "tokens": 1200},
            e0_primary),
        run(0, "emits-html-report", "old_skill",
            {"pass_rate": 0.2, "passed": 2, "failed": 8, "total": 10,
             "time_seconds": 45.0, "tokens": 900},
            e0_baseline),
        run(1, "summarises-csv", "with_skill",
            # This run had no timing.json. Absent, not zero.
            {"pass_rate": 1.0, "passed": 2, "failed": 0, "total": 2,
             "time_seconds": None, "tokens": None},
            e1_primary),
        run(1, "summarises-csv", "old_skill",
            {"pass_rate": 0.0, "passed": 0, "failed": 2, "total": 2,
             "time_seconds": 45.0, "tokens": 900},
            e1_baseline),
    ]

    benchmark = {
        # C5: roles are declared. "old_skill" sorts before "with_skill", which
        # is exactly what used to make the baseline the primary and invert the
        # delta in the improve flow.
        "primary": "with_skill",
        "baseline": "old_skill",
        "metadata": {
            "skill_name": "demo-skill",
            "skill_path": None,
            "executor_model": None,
            "analyzer_model": None,
            # Fields that used to reach innerHTML with no escaping at all.
            "timestamp": "2026-07-31T00:00:00Z " + svg("TS"),
            "evals_run": [0, 1, svg("EVALS")],
            "runs_per_configuration": 1,
            "runs_per_configuration_by_config": {"with_skill": 1, "old_skill": 1},
        },
        "runs": runs,
        "run_summary": {
            "with_skill": {
                # macro mean 0.75 against a pooled rate of 7/12 = 0.583
                "pass_rate": _stat(0.75, 0.3536, 0.5, 1.0, 2, 0),
                # one run had no timing.json: n=1, missing=1, stddev null
                "time_seconds": _stat(30.0, None, 30.0, 30.0, 1, 1),
                "tokens": _stat(1200.0, None, 1200, 1200, 1, 1),
                "runs": 2,
            },
            "old_skill": {
                "pass_rate": _stat(0.10, 0.1414, 0.0, 0.2, 2, 0),
                "time_seconds": _stat(45.0, 0.0, 45.0, 45.0, 2, 0),
                "tokens": _stat(900.0, 0.0, 900, 900, 2, 0),
                "runs": 2,
            },
            "delta": {
                "pass_rate": {"value": 0.65, "formatted": "+0.65",
                              "polarity": "higher_is_better", "better": True},
                # 15 seconds FASTER: negative sign, and it is good.
                "time_seconds": {"value": -15.0, "formatted": "-15.0",
                                 "polarity": "lower_is_better", "better": True},
                # 300 MORE tokens: positive sign, and it is bad.
                "tokens": {"value": 300.0, "formatted": "+300",
                           "polarity": "lower_is_better", "better": False},
            },
        },
        "exclusions": [
            {
                "path": "iteration-1/eval-2-dropped/with_skill/run-1/grading.json",
                "reason": "failed grading.json schema validation " + svg("EXCL"),
                "errors": ["expectations[0]: has 'met' but the viewer reads 'passed' - rename it"],
            },
        ],
        "layout_warnings": [
            "DEPRECATED LAYOUT: iteration-1/eval-3-flat/with_skill holds grading.json "
            "directly. Reading it as run-1. " + svg("LAYOUT"),
        ],
        "notes": [
            "Analyst note with markup: " + svg("NOTE"),
            "The skill is faster but uses more tokens.",
        ],
    }
    wj(base + "/benchmark.json", benchmark)

    # No declared roles: exercises the inference path and its warning.
    no_roles = json.loads(json.dumps(benchmark))
    del no_roles["primary"]
    del no_roles["baseline"]
    wj(base + "/benchmark-no-roles.json", no_roles)

    # The pre-rewrite shape: bare formatted-string deltas, no n/missing, no
    # exclusions, the hardcoded runs_per_configuration of 3, and an evals_run
    # that is not an array (which used to throw and blank the whole tab).
    legacy = json.loads(json.dumps(benchmark))
    for key in ("primary", "baseline", "exclusions", "layout_warnings"):
        del legacy[key]
    legacy["metadata"]["runs_per_configuration"] = 3
    del legacy["metadata"]["runs_per_configuration_by_config"]
    legacy["metadata"]["evals_run"] = "0, 1"
    for config in ("with_skill", "old_skill"):
        for metric in ("pass_rate", "time_seconds", "tokens"):
            stat = legacy["run_summary"][config][metric]
            legacy["run_summary"][config][metric] = {
                "mean": stat["mean"], "stddev": stat["stddev"] or 0.0,
                "min": stat["min"], "max": stat["max"],
            }
        del legacy["run_summary"][config]["runs"]
    legacy["run_summary"]["delta"] = {
        "pass_rate": "+0.65", "time_seconds": "-15.0", "tokens": "+300",
    }
    wj(base + "/benchmark-legacy.json", legacy)

    # =======================================================================
    # legacy-flat-workspace: no run-<K> level
    # =======================================================================
    flat = "legacy-flat-workspace/iteration-1/eval-0-flat-layout"
    wj(flat + "/eval_metadata.json", {
        "eval_id": 0, "eval_name": "flat-layout",
        "prompt": "Legacy flat layout probe. " + NONASCII,
    })
    for config, rate in (("with_skill", 1.0), ("without_skill", 0.5)):
        w(flat + "/" + config + "/outputs/out.txt", config + " output\n")
        passed = 2 if rate == 1.0 else 1
        wj(flat + "/" + config + "/grading.json", {
            "expectations": expectations(["Check A", "Check B"],
                                         [True, True] if rate == 1.0 else [True, False]),
            "summary": {"passed": passed, "failed": 2 - passed, "total": 2, "pass_rate": rate},
        })

    # =======================================================================
    # mixed-eval-id-workspace: identified, unidentified and null-id evals
    # =======================================================================
    mixed = "mixed-eval-id-workspace/iteration-1"
    wj(mixed + "/eval-0-has-metadata/eval_metadata.json",
       {"eval_id": 0, "eval_name": "has-metadata", "prompt": "Identified eval."})
    w(mixed + "/eval-0-has-metadata/with_skill/run-1/outputs/a.txt", "a\n")
    w(mixed + "/eval-1-no-metadata/with_skill/run-1/outputs/b.txt", "b\n")
    wj(mixed + "/eval-2-null-id/eval_metadata.json",
       {"eval_id": None, "eval_name": "null-id", "prompt": "Eval with a null id."})
    w(mixed + "/eval-2-null-id/with_skill/run-1/outputs/c.txt", "c\n")

    # =======================================================================
    # ordering-swap-workspace: the R10 repro
    #
    # One eval, two assertions, two configurations. Each configuration was
    # graded by its own sub-agent, and the two sub-agents returned the same two
    # checks in opposite order -- which nothing in the schema forbids, because
    # nothing in the schema promises an order. Each configuration passed ONE
    # check, and a DIFFERENT one.
    #
    #   with_skill:     [ HEADER pass, TOTALS fail ]
    #   without_skill:  [ TOTALS pass, HEADER fail ]
    #
    # Aligned by position, row 1 shows pass/pass and row 2 shows fail/fail: two
    # configurations in perfect agreement, which is the opposite of the truth.
    # Aligned by text, each row shows one pass and one fail.
    # =======================================================================
    HEADER = "Header row present"
    TOTALS = "Totals row is last"
    # A third check that one grader reworded, so the drift disclosure appears
    # on the same page as the ordering fix.
    CURRENCY = "Currency is formatted"
    CURRENCY_REWORDED = "The currency is formatted"

    swap = "ordering-swap-workspace/iteration-1/eval-0-swapped-order"
    wj(swap + "/eval_metadata.json", {
        "eval_id": 0,
        "eval_name": "swapped-order",
        "prompt": "Emit the sales table.",
        "assertions": [HEADER, TOTALS, CURRENCY],
    })

    swap_primary = [
        {"text": HEADER, "passed": True, "evidence": "row 1 is a header"},
        {"text": TOTALS, "passed": False, "evidence": "totals row is in the middle"},
        {"text": CURRENCY, "passed": True, "evidence": "GBP with two decimals"},
    ]
    swap_baseline = [
        {"text": TOTALS, "passed": True, "evidence": "totals row is last"},
        {"text": HEADER, "passed": False, "evidence": "no header row at all"},
        {"text": CURRENCY_REWORDED, "passed": False, "evidence": "bare integers"},
    ]

    for config, exps, rate in (("with_skill", swap_primary, 2 / 3),
                               ("without_skill", swap_baseline, 1 / 3)):
        w(swap + "/" + config + "/run-1/outputs/table.csv", config + ",1\n")
        passed = sum(1 for e in exps if e["passed"])
        wj(swap + "/" + config + "/run-1/grading.json", {
            "expectations": exps,
            "summary": {"passed": passed, "failed": len(exps) - passed,
                        "total": len(exps), "pass_rate": round(rate, 4)},
        })
        wj(swap + "/" + config + "/run-1/timing.json",
           {"total_tokens": 500, "duration_ms": 10000, "total_duration_seconds": 10.0})

    wj("ordering-swap-workspace/iteration-1/benchmark.json", {
        "primary": "with_skill",
        "baseline": "without_skill",
        "metadata": {
            "skill_name": "swap-demo",
            "timestamp": "2026-07-31T00:00:00Z",
            "evals_run": [0],
            "runs_per_configuration": 1,
        },
        "runs": [
            run(0, "swapped-order", "with_skill",
                {"pass_rate": 0.6667, "passed": 2, "failed": 1, "total": 3,
                 "time_seconds": 10.0, "tokens": 500},
                swap_primary),
            run(0, "swapped-order", "without_skill",
                {"pass_rate": 0.3333, "passed": 1, "failed": 2, "total": 3,
                 "time_seconds": 10.0, "tokens": 500},
                swap_baseline),
        ],
        # One run per configuration: stddev is null, and any renderer that
        # prints "+/- 0" here is inventing a spread it never measured.
        "run_summary": {
            "with_skill": {
                "pass_rate": _stat(0.6667, None, 0.6667, 0.6667, 1, 0),
                "time_seconds": _stat(10.0, None, 10.0, 10.0, 1, 0),
                "tokens": _stat(500.0, None, 500, 500, 1, 0),
                "runs": 1,
            },
            "without_skill": {
                "pass_rate": _stat(0.3333, None, 0.3333, 0.3333, 1, 0),
                "time_seconds": _stat(10.0, None, 10.0, 10.0, 1, 0),
                "tokens": _stat(500.0, None, 500, 500, 1, 0),
                "runs": 1,
            },
            "delta": {
                "pass_rate": {"value": 0.3334, "formatted": "+0.33",
                              "polarity": "higher_is_better", "better": True},
            },
        },
        "exclusions": [],
        "layout_warnings": [],
        "notes": [],
    })

    # The same benchmark with run_summary deleted: the viewer must recompute
    # from runs[] and must NOT print a standard deviation for a single sample.
    swap_bench = json.loads(
        (target / "ordering-swap-workspace/iteration-1/benchmark.json").read_text(encoding="utf-8"))
    no_summary = json.loads(json.dumps(swap_bench))
    del no_summary["run_summary"]
    wj("ordering-swap-workspace/iteration-1/benchmark-no-summary.json", no_summary)

    # And with a type-invalid run_summary: mean as a string, mean as null. The
    # viewer must reject the block, fall back, and SAY that it did.
    bad_summary = json.loads(json.dumps(swap_bench))
    bad_summary["run_summary"]["with_skill"]["pass_rate"]["mean"] = "67%"
    bad_summary["run_summary"]["without_skill"]["time_seconds"]["mean"] = None
    wj("ordering-swap-workspace/iteration-1/benchmark-bad-summary.json", bad_summary)

    # =======================================================================
    # malformed-run-workspace: run-final/ instead of run-1/
    # =======================================================================
    bad_run = "malformed-run-workspace/iteration-1/eval-0-misnamed-run"
    wj(bad_run + "/eval_metadata.json", {
        "eval_id": 0, "eval_name": "misnamed-run",
        "prompt": "Anything.", "assertions": ["Check A"],
    })
    w(bad_run + "/with_skill/run-final/outputs/out.txt", "with_skill output\n")
    wj(bad_run + "/with_skill/run-final/grading.json", {
        "expectations": [{"text": "Check A", "passed": True, "evidence": "it is there"}],
        "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
    })
    wj(bad_run + "/with_skill/run-final/timing.json",
       {"total_tokens": 100, "duration_ms": 1000, "total_duration_seconds": 1.0})
    w(bad_run + "/without_skill/run-1/outputs/out.txt", "without_skill output\n")
    wj(bad_run + "/without_skill/run-1/grading.json", {
        "expectations": [{"text": "Check A", "passed": False, "evidence": "absent"}],
        "summary": {"passed": 0, "failed": 1, "total": 1, "pass_rate": 0.0},
    })
    wj(bad_run + "/without_skill/run-1/timing.json",
       {"total_tokens": 100, "duration_ms": 1000, "total_duration_seconds": 1.0})

    # What aggregate_benchmark.py actually emits for the tree above, copied
    # from a real run of it: with_skill is excluded entirely, so NO primary
    # configuration produced a usable run. `primary` is null and the survivor
    # stays labelled baseline -- it is deliberately not promoted, and the
    # aggregation exits non-zero. The viewer must say the comparison is
    # incomplete rather than presenting the baseline as the subject, and must
    # not re-infer a primary that the aggregator explicitly declined to name.
    wj("malformed-run-workspace/iteration-1/benchmark.json", {
        "primary": None,
        "baseline": "without_skill",
        "metadata": {
            "skill_name": "misnamed",
            "timestamp": "2026-07-31T00:00:00Z",
            "evals_run": [0],
            "runs_per_configuration": 1,
            "runs_per_configuration_by_config": {"without_skill": 1},
        },
        "runs": [
            run(0, "misnamed-run", "without_skill",
                {"pass_rate": 0.0, "passed": 0, "failed": 1, "total": 1,
                 "time_seconds": 1.0, "tokens": 100},
                [{"text": "Check A", "passed": False, "evidence": "absent"}]),
        ],
        "run_summary": {
            "without_skill": {
                "pass_rate": _stat(0.0, None, 0.0, 0.0, 1, 0),
                "time_seconds": _stat(1.0, None, 1.0, 1.0, 1, 0),
                "tokens": _stat(100.0, None, 100, 100, 1, 0),
                "runs": 1,
            },
            "delta": {
                "pass_rate": {"value": None, "formatted": "—",
                              "polarity": "higher_is_better", "better": None},
            },
        },
        "exclusions": [
            {
                "path": "iteration-1/eval-0-misnamed-run/with_skill/run-final",
                "reason": "run directory `run-final` is not `run-<K>` with an integer K; "
                          "expected e.g. iteration-1/eval-0-misnamed-run/with_skill/run-1",
                "errors": [],
            },
            {
                "path": "iteration-1/eval-0-misnamed-run/without_skill/run-1",
                "reason": condition_line(
                    "unpaired_evals",
                    "eval 0 ran under `without_skill` but not under any primary "
                    "configuration - none produced a usable run, so it is excluded from "
                    "every delta. It still counts toward `without_skill`'s own column, "
                    "which is why the columns and the delta cover different evals here"),
                "errors": [],
            },
        ],
        "layout_warnings": [],
        "notes": [],
    })

    # =======================================================================
    # mixed-exclusions-workspace: all three exclusion KINDS on one page
    #
    # "Excluded" stopped being one thing. A blanket "excluded from every number
    # on this page" is now false for two of the three, and a reader who sees a
    # run listed as excluded while its pass rate plainly still counts concludes
    # the page is inconsistent when it is being precise.
    # =======================================================================
    mixed_x = "mixed-exclusions-workspace/iteration-1"
    for eval_id, slug in ((0, "fully-dropped"), (1, "timing-only"), (2, "unpaired")):
        base_dir = mixed_x + "/eval-%d-%s" % (eval_id, slug)
        wj(base_dir + "/eval_metadata.json", {
            "eval_id": eval_id, "eval_name": slug,
            "prompt": "Task %d." % eval_id, "assertions": ["Check A"],
        })
        configs = ("with_skill", "without_skill") if eval_id != 2 else ("with_skill",)
        for config in configs:
            w(base_dir + "/" + config + "/run-1/outputs/out.txt", config + "\n")
            wj(base_dir + "/" + config + "/run-1/grading.json", {
                "expectations": [{"text": "Check A", "passed": config == "with_skill",
                                  "evidence": "checked"}],
                "summary": {"passed": 1 if config == "with_skill" else 0,
                            "failed": 0 if config == "with_skill" else 1,
                            "total": 1, "pass_rate": 1.0 if config == "with_skill" else 0.0},
            })
            wj(base_dir + "/" + config + "/run-1/timing.json",
               {"total_tokens": 100, "duration_ms": 2000, "total_duration_seconds": 2.0})

    def mx_run(eval_id, name, config, rate, time_s, tokens):
        return run(eval_id, name, config,
                   {"pass_rate": rate, "passed": int(rate), "failed": 1 - int(rate),
                    "total": 1, "time_seconds": time_s, "tokens": tokens},
                   [{"text": "Check A", "passed": bool(rate), "evidence": "checked"}])

    wj(mixed_x + "/benchmark.json", {
        "primary": "with_skill",
        "baseline": "without_skill",
        "metadata": {
            "skill_name": "mixed-exclusions",
            "timestamp": "2026-07-31T00:00:00Z",
            "evals_run": [0, 1, 2],
            "runs_per_configuration": 1,
        },
        "runs": [
            # eval 0's with_skill run is gone entirely (schema-invalid grading).
            mx_run(0, "fully-dropped", "without_skill", 0.0, 2.0, 100),
            # eval 1 kept both gradings; one lost only its timing.
            mx_run(1, "timing-only", "with_skill", 1.0, None, None),
            mx_run(1, "timing-only", "without_skill", 0.0, 2.0, 100),
            # eval 2 ran under with_skill only: counted in its own column,
            # excluded from the delta.
            mx_run(2, "unpaired", "with_skill", 1.0, 2.0, 100),
        ],
        "run_summary": {
            "with_skill": {
                "pass_rate": _stat(1.0, 0.0, 1.0, 1.0, 2, 0),
                "time_seconds": _stat(2.0, None, 2.0, 2.0, 1, 1),
                "tokens": _stat(100.0, None, 100, 100, 1, 1),
                "runs": 2,
            },
            "without_skill": {
                "pass_rate": _stat(0.0, 0.0, 0.0, 0.0, 2, 0),
                "time_seconds": _stat(2.0, 0.0, 2.0, 2.0, 2, 0),
                "tokens": _stat(100.0, 0.0, 100, 100, 2, 0),
                "runs": 2,
            },
            "delta": {
                "pass_rate": {"value": 1.0, "formatted": "+1.00",
                              "polarity": "higher_is_better", "better": True},
            },
        },
        "exclusions": [
            # dropped: the whole run is out of every figure.
            {
                "path": "iteration-1/eval-0-fully-dropped/with_skill/run-1/grading.json",
                "reason": condition_line("schema_invalid",
                                         "failed grading.json schema validation"),
                "errors": ["expectations[0]: has 'met' but the viewer reads 'passed'"],
            },
            # timing only: the grading still counts.
            {
                "path": "iteration-1/eval-1-timing-only/with_skill/run-1/timing.json",
                "reason": condition_line(
                    "schema_invalid",
                    "failed timing.json schema validation, so this run's tokens and "
                    "duration are excluded and render as —. Its grading still counts"),
                "errors": ["total_tokens: -500 is negative"],
            },
            # pairing: out of the delta, in its own column.
            {
                "path": "iteration-1/eval-2-unpaired/with_skill/run-1",
                "reason": condition_line(
                    "unpaired_evals",
                    "eval 2 ran under `with_skill` but not under `without_skill`, so it "
                    "is excluded from every delta. It still counts toward `with_skill`'s "
                    "own column, which is why the columns and the delta cover different "
                    "evals here"),
                "errors": [],
            },
        ],
        "layout_warnings": [],
        "notes": [],
    })

    return target


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    build(target)
    print("eval-viewer fixtures written under " + str(target))


if __name__ == "__main__":
    main()

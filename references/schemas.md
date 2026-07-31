# JSON schemas

Every JSON artifact that crosses a boundary inside skill-creator: what writes it, what reads it, what
its fields are called, and which checker proves you got it right.

Field names here are **binding and case-sensitive**. They are the same names `scripts/validate_grading.py`
enforces and `agents/*.md` emit. Where this document and any script, prose, or agent prompt disagree,
the disagreement is a bug in one of them — not a choice.

## Contents

Sections run in the order you meet the artifacts.

| # | Artifact | Written by | Checked by |
|---|---|---|---|
| [1](#1-where-these-files-live) | Workspace layout | you, as you go | `scripts.validate_grading` |
| [2](#2-evalsevalsjson) | `evals/evals.json` | you | none |
| [3](#3-eval_metadatajson) | `eval_metadata.json` | you | `scripts.validate_grading` |
| [4](#4-run-outputs) | `outputs/`, `transcript.md`, `user_notes.md` | the run sub-agent | none |
| [5](#5-timingjson) | `timing.json` | you, from the task notification | `scripts.validate_grading` |
| [6](#6-gradingjson) | `grading.json` | the grader sub-agent | `scripts.validate_grading` |
| [7](#7-benchmarkjson-and-benchmarkmd) | `benchmark.json`, `benchmark.md` | `scripts.aggregate_benchmark` | build-time only |
| [8](#8-feedbackjson) | `feedback.json` | the viewer | none |
| [9](#9-blind-comparison-artifacts) | `assignment_key.json`, `comparison.json`, `analysis.json` | you, the comparator, the analyzer | build-time only |
| [10](#10-description-optimization-artifacts) | trigger eval set, optimizer `results.json` | `assets/eval_review.html`, `scripts.run_loop` | none |
| [11](#11-assertions-vs-expectations) | the one word that means two things | — | — |
| [12](#12-what-is-checked-and-what-is-not) | checker coverage | — | — |

**How to read the examples.** Braced names like `{Assertion_Copied_Character_For_Character}` are
**slots, not values** — replace each with a value of the type its field description names. Field
names, the key hierarchy, the JSON types and the closed enums are fixed and copied exactly; those are
invariant across every run and are what this document exists to pin down. Anything a model would have
to *judge* — verdict text, evidence, rationale, findings — is a slot, and the few numbers that must
stay literal for a checker to run are deliberately round and deliberately fake. A concrete value at
those positions gets copied into a real artifact and then read as a measurement.

Every example was run through the checker named in its section. "Build-time only" means no script
inspects the file you produce, but `tests.test_agent_prompt_contracts` compares its documented shape
against `agents/*.md` and the consumers — see [§12](#12-what-is-checked-and-what-is-not) for which
kind of check covers what.

---

## 1. Where these files live

One layout. `run-<K>/` is always present — a single run is `run-1/`, never a flattened config directory.

```
<skill-name>-workspace/
└── iteration-<N>/
    ├── benchmark.json
    ├── benchmark.md
    ├── feedback.json
    └── eval-<ID>-<descriptive-slug>/
        ├── eval_metadata.json
        └── <config>/                     # with_skill | without_skill | old_skill
            └── run-<K>/                  # ALWAYS present, even for one run: run-1
                ├── outputs/
                ├── grading.json
                └── timing.json
```

`ID` is an integer and **must equal** that eval's `eval_metadata.json` `eval_id`; the validator
compares them. The slug is the same string as `eval_name`, and it is lowercase, digits and hyphens —
a directory that does not match `eval-<ID>-<slug>` is reachable only if it happens to carry an
`eval_metadata.json`, and is warned about either way.

Readers may additionally accept the legacy flat layout (a config directory holding `grading.json`
directly, with no `run-<K>/` level), but only by normalizing it to `run-1` and saying so out loud. A
grading file the aggregator cannot reach is an error, not a warning:

```
$ python -m scripts.validate_grading <workspace>/iteration-1
OK   ...\eval-0-<slug>\with_skill\run-1\grading.json
OK   ...\eval-0-<slug>\without_skill\run-1\grading.json
OK   ...\eval-0-<slug>\eval_metadata.json

2 grading file(s): 2 canonical, 0 legacy-flat, 0 unreachable.
All 2 grading file(s) valid.
```

**Absent data is absent, never zero.** No reader substitutes a default that renders as a legitimate
measurement. A missing `timing.json` makes the token and duration cells read `—` (unknown), not `0`.
Zero discovered runs makes `aggregate_benchmark` exit non-zero rather than write a benchmark of zeros.
A grading file that fails validation is named, counted, and excluded from aggregation, and the
exclusion is visible in the result.

---

## 2. `evals/evals.json`

The durable record of a skill's test cases, kept inside the skill directory at `evals/evals.json` so
it survives across iterations and across workspaces.

```json
{
  "skill_name": "{Skill_Name_From_The_Frontmatter}",
  "evals": [
    {
      "id": 0,
      "prompt": "{The_Task_Handed_To_Both_Configurations_Verbatim}",
      "expected_output": "{One_Sentence_Describing_What_Success_Looks_Like}",
      "files": ["{Input_Path_Relative_To_The_Skill_Root}"],
      "assertions": [
        "{Objectively_Verifiable_Statement_About_The_Output}"
      ]
    }
  ]
}
```

**Fields**

- `skill_name` — string. Matches the skill's frontmatter `name`.
- `evals[].id` — integer. The same integer as the eval directory's `<ID>` and `eval_metadata.json`'s
  `eval_id`.
- `evals[].prompt` — string. The task handed to both configurations, verbatim.
- `evals[].expected_output` — string. Human-readable description of success. Not machine-read.
- `evals[].files` — array of strings, optional. Input file paths relative to the skill root.
- `evals[].assertions` — array of strings. The input set you write. It becomes
  `eval_metadata.json`'s `assertions`, and the grader returns the same statements as
  `grading.json`'s `expectations`. See [§11](#11-assertions-vs-expectations).

**Who reads it:** no script and no agent prompt. It is read by you, at the start of the next
iteration, which is the whole point of keeping it. Copy `assertions` from here into each
`eval_metadata.json` rather than re-drafting them — re-drafting is how assertion text drifts, and
drifted text splits one assertion into two half-empty rows in the comparison table.

**Checker:** none. Nothing validates this file.

---

## 3. `eval_metadata.json`

One per eval directory, at `<eval-dir>/eval_metadata.json` — beside the config directories, not inside
them. This is the most placement-sensitive file in the workspace: the aggregator reads it from the
eval directory, and the viewer searches upward from each run directory to find it.

```json
{
  "eval_id": 0,
  "eval_name": "{Descriptive_Slug_Matching_The_Directory_Suffix}",
  "prompt": "{The_Task_Handed_To_Both_Configurations_Verbatim}",
  "assertions": [
    "{Objectively_Verifiable_Statement_About_The_Output}",
    "{Second_Objectively_Verifiable_Statement}"
  ]
}
```

**Fields**

- `eval_id` — JSON integer, required. Must equal the `<ID>` in the directory name. A string here
  breaks the sort in every consumer.
- `eval_name` — non-empty string, required. The descriptive slug, without the `eval-<ID>-` prefix.
  It is the section header for this eval in the rendered benchmark; when it is missing the section
  reads "Eval 0".
- `prompt` — non-empty string, required. What the run was asked to do. The viewer shows it above the
  outputs, and it is the only context a human reviewer has for judging them.
- `assertions` — array of strings. The input set. Write it as soon as it is drafted; an empty array
  while runs are still in flight is normal, a still-empty array at grading time is not.

Write one of these for every eval directory in every iteration. They do not carry over — an eval
directory without one leaves its runs unlabeled and unexplained.

**Who reads it:** `scripts/aggregate_benchmark.py` (for `eval_id` and `eval_name`),
`eval-viewer/generate_review.py` (for `prompt` and `eval_id`), and `scripts/validate_grading.py`.

**Checker:** `python -m scripts.validate_grading <iteration-dir>` validates every
`eval_metadata.json` beside a graded run, including the `eval_id` ↔ directory-name agreement. The
example above validated `OK` as part of the workspace in [§1](#1-where-these-files-live).

---

## 4. Run outputs

`run-<K>/outputs/` holds whatever the run was asked to produce — the `.docx`, the CSV, the chart. The
viewer renders these inline; there is no schema.

Two optional non-JSON files may sit beside them, and both exist only if your spawn prompt asked the
run sub-agent for them:

- `transcript.md` — the execution record. The grader uses it as secondary evidence when the outputs
  alone cannot settle an expectation; the viewer falls back to a `## Eval Prompt` section in it when
  no `eval_metadata.json` can be found. Optional everywhere, and frequently absent.
- `user_notes.md` — uncertainties and workarounds the run recorded about its own work. The grader
  summarizes it into `grading.json`'s `user_notes_summary`.

Both are excluded from the viewer's output listing rather than shown as deliverables.

There is **no `metrics.json`**. Earlier versions of this document specified one, described as the
output of an executor agent; no such agent exists, nothing ever wrote the file, and the grader block
that consumed it (`execution_metrics`) was retired because its `output_chars` was being published
under the heading "Tokens". Token counts come from `timing.json` and from nowhere else.

`execution_metrics` is now read by nothing, anywhere in the bundle. That is pinned by a test in the
aggregator's suite: a fixture carrying a full `execution_metrics` block asserts the block stays
inert. So if you open an old workspace and find one, it is **ignored, not misparsed** — no column
downstream is derived from it, and deleting it changes no number. The same goes for the
`tool_calls`, `errors` and `output_chars` fields it used to feed, which no longer appear in
`benchmark.json` at all ([§7](#7-benchmarkjson-and-benchmarkmd)).

**Checker:** none.

---

## 5. `timing.json`

Wall-clock and token cost for one run, at `run-<K>/timing.json`.

**How to capture it:** when a run sub-agent's task completes, the notification carries `total_tokens`
and `duration_ms`. Write them down immediately. They are not persisted anywhere else and cannot be
recovered afterwards — this is the only moment the data exists.

```json
{
  "total_tokens": 1000,
  "duration_ms": 2000,
  "total_duration_seconds": 2.0
}
```

The three values are deliberately round and deliberately fake — they are here to show the types, not a
measurement. Write what the notification actually reported. A number copied out of this document is
indistinguishable downstream from one you observed, which is the whole reason the token column was
wrong for so long.

**Fields**

- `total_tokens` — JSON integer, non-negative. The run's token cost. This is the only source for the
  benchmark's token column.
- `duration_ms` — JSON integer, non-negative. Duration as the notification reported it.
- `total_duration_seconds` — JSON number, non-negative. `duration_ms / 1000`, to one decimal.

No other keys. Earlier versions listed `executor_start`, `executor_end`, `grader_start`, `grader_end`,
`executor_duration_seconds` and `grader_duration_seconds`; nothing has ever read them.

If the file is missing, every field it feeds renders as `—`. It is never treated as zero, and a zero
you write by hand is indistinguishable from a real measurement of zero — so omit the file rather than
inventing values for it.

**Who reads it:** `scripts/aggregate_benchmark.py`, unconditionally, for both the token and the
duration column. `scripts/validate_grading.py` validates it.

**Checker:** `python -m scripts.validate_grading <iteration-dir>`. It type-checks all three fields,
rejects negatives, and warns per-field when one is absent, naming the cell that will render `—`.

---

## 6. `grading.json`

The grader sub-agent's verdict for one run, at `run-<K>/grading.json`. This is the file the whole
quantitative side of the loop rests on, and the one whose field names are most often wrong.

### Required shape

```json
{
  "expectations": [
    {
      "text": "{Assertion_Copied_Character_For_Character_From_eval_metadata_assertions}",
      "passed": true,
      "evidence": "{Quoted_Text_Or_File_State_Another_Reader_Could_Recheck}"
    },
    {
      "text": "{Second_Assertion_Copied_Character_For_Character}",
      "passed": false,
      "evidence": "{Which_Evidence_Was_Missing_Or_Which_Evidence_Contradicted_It}"
    }
  ],
  "summary": {
    "passed": 1,
    "failed": 1,
    "total": 2,
    "pass_rate": 0.5
  }
}
```

The booleans, the integers and `pass_rate` are literal because their **types** are the contract and
the validator checks the arithmetic between them. Everything a grader would have to judge is a slot.

**Fields**

- `expectations[]` — array, one entry per assertion, in the order the grader received them.
  - `text` — string. The assertion **copied character-for-character** from `eval_metadata.json`. The
    comparison table lines expectations up across configurations by exact string equality; one
    reworded word splits a single assertion into two half-filled rows that read as "never evaluated".
  - `passed` — JSON boolean. Not `"true"`. A string is truthy everywhere downstream, so a
    string-typed `passed` corrupts results rather than merely looking untidy.
  - `evidence` — string. The quote or file observation behind the verdict. Required: a graded result
    without it cannot be rechecked.
- `summary` — aggregate counts over `expectations`.
  - `passed`, `failed`, `total` — JSON integers. `passed + failed == total == len(expectations)`.
    All three equalities are enforced.
  - `pass_rate` — JSON number in `[0.0, 1.0]`. Never a string, never a percentage. It is checked
    against the expectations array with a tolerance of 0.01, so a rounded two-decimal value for a
    repeating fraction is accepted.

### Optional blocks

`claims`, `user_notes_summary`, and `eval_feedback` are written only when the grader has something
substantive for them. Omission is a normal outcome.

```json
{
  "expectations": [
    {
      "text": "{Assertion_Copied_Character_For_Character_From_eval_metadata_assertions}",
      "passed": true,
      "evidence": "{Quoted_Text_Or_File_State_Another_Reader_Could_Recheck}"
    },
    {
      "text": "{Second_Assertion_Copied_Character_For_Character}",
      "passed": false,
      "evidence": "{Which_Evidence_Was_Missing_Or_Which_Evidence_Contradicted_It}"
    }
  ],
  "summary": {
    "passed": 1,
    "failed": 1,
    "total": 2,
    "pass_rate": 0.5
  },
  "claims": [
    {
      "claim": "{Statement_The_Output_Or_Transcript_Made_About_Itself}",
      "type": "factual | process | quality",
      "verified": false,
      "evidence": "{What_Was_Checked_And_What_Was_Found_Instead}"
    }
  ],
  "user_notes_summary": {
    "uncertainties": ["{Concern_The_Run_Recorded_About_Its_Own_Work}"],
    "needs_review": [],
    "workarounds": ["{Place_The_Run_Reported_Departing_From_The_Skill}"]
  },
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "{Assertion_Text_This_Concerns}",
        "reason": "{What_A_Wrong_Output_Could_Do_And_Still_Satisfy_This_Assertion}"
      }
    ],
    "overall": "{One_Sentence_On_Whether_This_Set_Discriminates}"
  }
}
```

- `claims[]` — statements the outputs or transcript made about themselves that the grader checked.
  `type` is one of `factual`, `process`, `quality`. `verified` is a boolean.
- `user_notes_summary` — three string arrays, `uncertainties`, `needs_review`, `workarounds`. The
  aggregator flattens all three into that run's `notes`.
- `eval_feedback` — the grader's critique of the assertion set. `suggestions[].assertion` may be
  omitted when the point is a gap rather than a specific assertion. Read by you, by hand, when
  revising `evals/evals.json`; no script reads it.

### Blocks that must not appear

- **`timing`.** Timing lives only in `timing.json`. A `timing` block here used to take precedence over
  that file and close the only path the token count could travel, so the benchmark reported the wrong
  number for every configuration.
- **`execution_metrics`.** Its `output_chars` is a character count, and it reached the benchmark under
  the heading "Tokens". Characters run roughly 4× tokens, so the number always looked plausible.

Both are warnings rather than errors today — they are ignored rather than obeyed, and a test pins
`execution_metrics` as inert — but a grader that writes either is not following `agents/grader.md`.

**Who reads it:** `scripts/aggregate_benchmark.py`, `scripts/validate_grading.py`, and the viewer's
Formal Grades panel and per-eval comparison table.

**Checker:** `python -m scripts.validate_grading <path>`, where `<path>` is a single `grading.json` or
an iteration directory to walk. It checks placement against [§1](#1-where-these-files-live), the field
names (including the aliases graders reach for — `met`, `result`, `success` for `passed`; `name`,
`assertion`, `description` for `text`; `details`, `reason`, `justification` for `evidence`), the JSON
types, and the summary arithmetic. Exits non-zero on any error. Run it before aggregating; a wrong
field name does not raise on its own, it aggregates to a clean, plausible, wrong number.

---

## 7. `benchmark.json` and `benchmark.md`

Produced by `python -m scripts.aggregate_benchmark <iteration-dir> --skill-name <name>`, written to
`iteration-<N>/benchmark.json` and `iteration-<N>/benchmark.md`. `benchmark.md` is the same data
rendered for a human to paste somewhere; it has no schema and nothing reads it back.

**The two files format deltas differently, deliberately.** `benchmark.json` keeps the raw number;
`benchmark.md` adds the row's unit:

| Metric | `benchmark.json` `formatted` | `benchmark.md` delta cell |
|---|---|---|
| `pass_rate` | `+0.75` | `+75 pp` |
| `time_seconds` | `+30.0` | `+30.0s` |
| `tokens` | `+40000` | `+40000 tokens` |

The JSON is read by code, which needs a number it can parse and compare — `pass_rate` stays the
`0.0`–`1.0` fraction it is everywhere else in the schema. The markdown is read by a person, for whom
a bare `+0.75` next to a row labelled with percentages is ambiguous between a fraction and a
percentage. `pp` is percentage *points*, the difference between two percentages. Do not "fix" either
one to match the other. `benchmark.md`'s per-eval table also carries a `Paired` column (`yes`/`no`)
that has no JSON counterpart — the JSON records the same fact as an `exclusions` entry.

The block below is the aggregator's own output, reproduced verbatim, over a two-configuration
workspace built from the `grading.json` and `timing.json` frames in [§5](#5-timingjson) and
[§6](#6-gradingjson). The slots carried straight through, so what you see is the real key hierarchy
with no invented content in it.

```json
{
  "primary": "with_skill",
  "baseline": "without_skill",
  "metadata": {
    "skill_name": "{Skill_Name_From_The_Frontmatter}",
    "skill_path": null,
    "executor_model": null,
    "analyzer_model": null,
    "timestamp": "2026-07-31T05:48:54Z",
    "evals_run": [0],
    "runs_per_configuration": 1,
    "runs_per_configuration_by_config": {"with_skill": 1, "without_skill": 1}
  },
  "runs": [
    {
      "eval_id": 0,
      "eval_name": "{Descriptive_Slug_Matching_The_Directory_Suffix}",
      "configuration": "with_skill",
      "run_number": 1,
      "result": {"pass_rate": 0.5, "passed": 1, "failed": 1, "total": 2, "time_seconds": 2.0, "tokens": 1000},
      "expectations": [
        {"text": "{Assertion_Copied_Character_For_Character_From_eval_metadata_assertions}", "passed": true, "evidence": "{Quoted_Text_Or_File_State_Another_Reader_Could_Recheck}"},
        {"text": "{Second_Assertion_Copied_Character_For_Character}", "passed": false, "evidence": "{Which_Evidence_Was_Missing_Or_Which_Evidence_Contradicted_It}"}
      ],
      "notes": []
    },
    {
      "eval_id": 0,
      "eval_name": "{Descriptive_Slug_Matching_The_Directory_Suffix}",
      "configuration": "without_skill",
      "run_number": 1,
      "result": {"pass_rate": 0.0, "passed": 0, "failed": 2, "total": 2, "time_seconds": 1.0, "tokens": 2000},
      "expectations": [
        {"text": "{Assertion_Copied_Character_For_Character_From_eval_metadata_assertions}", "passed": false, "evidence": "{Quoted_Text_Or_File_State_Another_Reader_Could_Recheck}"},
        {"text": "{Second_Assertion_Copied_Character_For_Character}", "passed": false, "evidence": "{Which_Evidence_Was_Missing_Or_Which_Evidence_Contradicted_It}"}
      ],
      "notes": []
    }
  ],
  "run_summary": {
    "with_skill": {
      "pass_rate": {"mean": 0.5, "stddev": null, "min": 0.5, "max": 0.5, "n": 1, "missing": 0},
      "time_seconds": {"mean": 2.0, "stddev": null, "min": 2.0, "max": 2.0, "n": 1, "missing": 0},
      "tokens": {"mean": 1000.0, "stddev": null, "min": 1000, "max": 1000, "n": 1, "missing": 0},
      "runs": 1
    },
    "without_skill": {
      "pass_rate": {"mean": 0.0, "stddev": null, "min": 0.0, "max": 0.0, "n": 1, "missing": 0},
      "time_seconds": {"mean": 1.0, "stddev": null, "min": 1.0, "max": 1.0, "n": 1, "missing": 0},
      "tokens": {"mean": 2000.0, "stddev": null, "min": 2000, "max": 2000, "n": 1, "missing": 0},
      "runs": 1
    },
    "delta": {
      "pass_rate": {"value": 0.5, "formatted": "+0.50", "polarity": "higher_is_better", "better": true},
      "time_seconds": {"value": 1.0, "formatted": "+1.0", "polarity": "lower_is_better", "better": false},
      "tokens": {"value": -1000.0, "formatted": "-1000", "polarity": "lower_is_better", "better": true}
    }
  },
  "exclusions": [],
  "layout_warnings": [],
  "notes": []
}
```

### Comparison direction

`primary` and `baseline` name the two configurations **by role**, at the top level of the file and
nowhere else. They are never derived from `sorted()`: `old_skill` sorts before `with_skill`, so
alphabetical ordering makes the baseline primary and prints a genuine improvement as a regression.

- `primary` — the configuration under test: `with_skill`, or `new_skill`.
- `baseline` — what it is measured against: `without_skill`, or `old_skill`. `null` when only one
  configuration produced usable runs.
- Every delta is `primary − baseline`.

**`primary` can be `null`, and a surviving baseline is never promoted into it.** When no
primary-role configuration produced a usable run — the directory is absent, or everything in it was
excluded — the survivor keeps its own role. It is labelled `[baseline]`, `primary` is `null`, every
delta is `—`, and the aggregation exits 1.

Promotion is the tempting behaviour and it is the wrong one. A promoted survivor produces an artifact
that reads as a perfectly ordinary single-configuration result: one column, real numbers, nothing
visibly missing. Someone skimming it has no reason to suspect the comparison lost half its data — and
the half it lost is the half the whole run existed to measure. Leaving `primary` null makes the hole
the first thing in the file. If a workspace really is a single-configuration record, say so
explicitly with `--primary` / `--baseline` rather than letting the aggregator infer it.

Each metric declares its polarity, and presentation colors by *goodness*, not by sign:

| Metric | Polarity | Meaning |
|---|---|---|
| `pass_rate` | `higher_is_better` | a positive delta is good |
| `time_seconds` | `lower_is_better` | a negative delta is good |
| `tokens` | `lower_is_better` | a negative delta is good |

That declaration lives in exactly one place: `run_summary.delta.<metric>.polarity`. There is no
top-level polarity map. Two copies of the same fact are a drift surface, and per-delta is the form a
renderer actually consumes.

`run_summary.delta.<metric>` therefore carries the judgment already made: `value` is the raw
`primary − baseline` number, `formatted` is the signed string to display, `polarity` is the metric's
direction, and `better` is the boolean a renderer colors on. In the block above the token delta is
negative and `better` is `true`, while the duration delta is positive and `better` is `false` — the
sign and the judgment point opposite ways, which is the entire reason `better` is computed here
rather than inferred by whatever draws the table. When either side has no usable runs, `value` and
`better` are `null` and `formatted` is `—`.

### Fields

- `metadata.skill_name` / `skill_path` — strings identifying what was benchmarked; `skill_path` is
  `null` when `--skill-path` was not given. Never a placeholder string like `<path/to/skill>`, which
  renders in `benchmark.md` as if it were data.
- `metadata.executor_model` / `analyzer_model` — the model ids actually used, or `null` when unknown.
- `metadata.timestamp` — UTC ISO 8601, `YYYY-MM-DDTHH:MM:SSZ`.
- `metadata.evals_run` — array of the `eval_id` integers found.
- `metadata.runs_per_configuration` — derived from the `run-<K>` directories actually discovered,
  never a constant. `runs_per_configuration_by_config` gives the per-configuration counts, which is
  what you need when the two sides did not run the same number of times.
- `runs[]` — one entry per run.
  - `eval_id` — integer, from `eval_metadata.json`.
  - `eval_name` — string, from `eval_metadata.json`. The viewer uses it as the per-eval section
    header and falls back to `"Eval " + eval_id` when it is absent.
  - `configuration` — the config directory name, discovered from the data. `with_skill`,
    `without_skill` and `old_skill` are the recognized names; the viewer groups and colors by this
    exact string.
  - `run_number` — the integer `K` from `run-<K>`.
  - `result` — exactly `pass_rate`, `passed`, `failed`, `total` from `grading.json`'s `summary`, plus
    `time_seconds` and `tokens` from `timing.json`. Nothing else. **A value with no source for this
    particular run is `null`, never `0`** — a missing `timing.json` gives `"tokens": null`, and the
    cell renders `—`.

    `output_chars`, `tool_calls` and `errors` used to sit here and are now **gone**, not nulled.
    Their only source was the `execution_metrics` block, which was fed by `metrics.json`, which never
    had a producer ([§4](#4-run-outputs)). With the producer gone they were unmeasurable in every
    workspace, forever — and a field that is permanently `null` reads as a measurement that came back
    empty, which is the same class of lie as a `0`. `null` is for data that could have been there
    this time and was not; absence is for data that can never be there. Do not add them back by hand.
  - `expectations` — passed through from `grading.json` unchanged.
  - `notes` — the run's `user_notes_summary` arrays, flattened into one array of strings.
- `run_summary.<config>` — per-configuration `pass_rate`, `time_seconds` and `tokens`, each with
  `mean`, `stddev`, `min`, `max`, plus `n` (runs that contributed a value) and `missing` (runs that
  had none). `stddev` is the sample (n−1) standard deviation and is `null` — not `0.0` — when `n` is
  1, because one sample has no spread to report. `runs` is the configuration's total run count.
- `exclusions` — one object per run left out of the statistics, each with `path`, a one-line
  `reason`, and `errors`. The omission is visible in the artifact, not only in a console line that
  scrolled past. `reason` opens with a `[C12:<condition>=<severity>]` token, the same token the
  validator and preflight print, so three tools' verdicts on one workspace can be diffed rather than
  trusted.

  Two kinds of entry land here, and `path` tells you which:

  **A file that failed schema validation.** `path` is the offending `grading.json` or `timing.json`,
  and `errors` carries the validator's messages.

  ```json
  {
    "path": "...\\eval-0-broken\\with_skill\\run-1\\grading.json",
    "reason": "[C12:schema_invalid=error] ... failed grading.json schema validation",
    "errors": [
      "expectations[0]: has 'met' but the viewer reads 'passed' - rename it",
      "summary.pass_rate: must be a number in [0.0, 1.0], got str ('100%')"
    ]
  }
  ```

  **A run that could not be paired.** `path` is the **run directory**, and `errors` is empty —
  nothing was malformed. This fires when an eval ran under one configuration and not its counterpart,
  or when excluding a file left the two sides with different surviving runs.

  ```json
  {
    "path": "...\\eval-1-only-primary\\with_skill\\run-1",
    "reason": "[C12:unpaired_evals=error] ... eval 1 ran under `with_skill` but not under `without_skill`, so it is excluded from every delta",
    "errors": []
  }
  ```

  An unpaired run still counts toward its own configuration's column; it is only kept out of the
  delta, because a difference computed over an eval the baseline never attempted is a difference the
  baseline never had the chance to produce.

  Pairing failures live in `exclusions` rather than in a key of their own **on purpose**. They *are*
  exclusions — runs that were found and then left out. A separate key would let someone who checks
  `exclusions`, sees `[]`, and moves on conclude that nothing was dropped.

- `layout_warnings` — array of strings describing directories that were interpreted rather than read
  literally, such as a legacy flat config directory normalized to `run-1`.
- `notes` — array of plain strings, at the **top level**, a sibling of `metadata` / `runs` /
  `run_summary`. The viewer renders it under "Analysis Notes" and renders nothing when it is empty.

  **Re-aggregation is the only thing that writes this key.** The analyst pass writes its array to a
  separate notes file and the caller then re-runs the aggregator with `--notes`:

  ```bash
  python -m scripts.aggregate_benchmark <iteration-dir> --skill-name <name> --notes <notes-path>
  ```

  That run rebuilds the whole file from the runs and embeds the array in both `benchmark.json`'s
  `notes` and `benchmark.md`'s `## Notes` section. Two consequences follow, and both are load-bearing:

  - **A hand edit to `benchmark.json` is silently lost.** The next aggregation overwrites the object
    it was made to. Verified: hand-setting `notes` and re-running without `--notes` returns `[]`.
  - **A notes file that is never passed to `--notes` has no reader at all.** The panel stays blank
    and the pass produced nothing. Verified: `## Notes` appears in `benchmark.md` after a `--notes`
    run and disappears again on the next plain re-aggregation.

  So the order is: aggregate → analyst writes the notes file → aggregate again with `--notes`. Not
  aggregate → edit.

Zero discovered runs is a failure, not an empty benchmark: the aggregator exits non-zero, prints the
paths it searched and the layout it expected, and writes nothing.

**Who reads it:** `eval-viewer/viewer.html`, via `eval-viewer/generate_review.py --benchmark`, and
`agents/analyzer.md`'s benchmark mode, which reads it and treats it as read-only.

**Checker:** no runtime validator — this file is written by a script rather than by a model, so the
leverage sits in the script, and the example above is that script's own output. There is a
build-time check: `python -m unittest tests.test_agent_prompt_contracts` diffs this section's
top-level keys and `runs[].result` against what the aggregator emits and against the eight keys
`agents/analyzer.md` tells the analyst to expect.

The aggregator's own exit code is the signal that matters at runtime, and `0` does **not** mean
nothing was dropped — see [§12](#12-what-is-checked-and-what-is-not). If you ever generate this file
by hand, match the shape exactly: using `config` instead of `configuration`, or lifting `pass_rate`
out of `result`, makes the viewer render zeros rather than complain.

---

## 8. `feedback.json`

Written by the viewer when the user clicks "Submit All Reviews", to `iteration-<N>/feedback.json` —
the same directory that was passed to `generate_review.py`.

```json
{
  "reviews": [
    {
      "run_id": "eval-0-<slug>-with_skill-run-1",
      "feedback": "{What_The_User_Typed_About_This_Run}",
      "timestamp": "{ISO_8601_Timestamp}"
    },
    {
      "run_id": "eval-0-<slug>-without_skill-run-1",
      "feedback": "",
      "timestamp": "{ISO_8601_Timestamp}"
    }
  ],
  "status": "complete"
}
```

**Fields**

- `reviews[].run_id` — the run directory's path relative to the iteration directory, with separators
  replaced by `-`. Under the canonical layout that is
  `eval-<ID>-<slug>-<config>-run-<K>`. Both sides compute it the same way, on Windows and POSIX
  alike.
- `reviews[].feedback` — string. **An empty string means "reviewed, looks fine".** That is different
  from a `run_id` that is absent, which means "not reviewed". Do not collapse the two.
- `reviews[].timestamp` — ISO 8601 string. Not read by anything.
- `status` — `"in_progress"` while the user is typing (auto-save writes only non-empty entries), or
  `"complete"` on submit (which writes an entry for **every** run, including the empty ones).

In a headless or static run the browser downloads this file instead of POSTing it; copy it into the
iteration directory for the next iteration to pick up.

**Who reads it:** `eval-viewer/generate_review.py` when passed `--previous-workspace`, which maps
`run_id` → `feedback` to show last iteration's comments beside this iteration's outputs. It reads
`run_id` and `feedback` only, and skips entries whose `feedback` is blank.

**Checker:** none. The server-side POST handler rejects a body that is not an object with a `reviews`
key, which is the only structural guard.

---

## 9. Blind comparison artifacts

Optional, and most iterations never reach this. See `agents/comparator.md` and `agents/analyzer.md`.
All three files live under `iteration-<N>/comparisons/eval-<ID>/`.

### `assignment_key.json`

Written by **you**, during the de-identification step, before the comparator is spawned. It is the
record of which candidate label maps to which configuration — and the comparator must never receive
it or its path.

```json
{
  "A": {
    "configuration": "with_skill | without_skill | old_skill",
    "path": "{Comparison_Dir}/candidates/{Random_Token}"
  },
  "B": {
    "configuration": "with_skill | without_skill | old_skill",
    "path": "{Comparison_Dir}/candidates/{Random_Token}"
  },
  "seed": 0,
  "swapped": false,
  "draw": "sorted(configs), reversed when random.Random(seed).random() < 0.5"
}
```

**Fields**

- `A` / `B` — the label → configuration mapping, each with the neutral candidate directory the
  comparator is given.
- `seed` — JSON integer, from `secrets.randbits(64)`. Unpredictable in advance, recorded so the draw
  can be replayed afterwards.
- `swapped` — JSON boolean. Whether the draw reversed the pre-draw order.
- `draw` — string. The rule that turns `seed` into the mapping, stated well enough to rerun.

The three audit fields are what make blinding *checkable* rather than merely asserted. Anyone can
recompute `random.Random(seed).random() < 0.5` against `sorted(configs)` and confirm the labels
landed where the key says they did. If the replay disagrees, the assignment was **chosen rather than
drawn** — a hand-picked or alternating A/B is otherwise indistinguishable from a fair one after the
fact, because nothing in the comparator's output reveals it. An unreplayable seed is a record of
nothing.

Two details in the reference implementation are load-bearing for that property, and neither is
arbitrary:

- The draw goes through `random()`, not `getrandbits()`. The standard library guarantees `random()`
  reproduces for a given integer seed across Python versions and promises nothing of the sort for the
  others.
- The pre-draw order is `sorted(configs)`, not dict insertion order, so a replay does not depend on
  the order the caller happened to build its argument in.

Resolve `winner` back through this file after the comparator returns.

### `comparison.json`

Written by the comparator to the `output_path` it was given. The field names, the key hierarchy, the
six rubric criteria and the `winner` enum are fixed; the braced names below are **slots, not values**,
copied from `agents/comparator.md`, which is the authority for this shape.

```json
{
  "winner": "A | B | TIE",
  "reasoning": "{Two_To_Four_Sentences_Naming_The_Concrete_Differences_That_Decided_It}",
  "rubric": {
    "A": {
      "content": {
        "correctness": "{1_To_5}",
        "completeness": "{1_To_5}",
        "accuracy": "{1_To_5}"
      },
      "structure": {
        "organization": "{1_To_5}",
        "formatting": "{1_To_5}",
        "usability": "{1_To_5}"
      },
      "task_specific": {
        "{Snake_Case_Criterion_This_Task_Needs_That_The_Six_Do_Not_Reach}": "{1_To_5}"
      },
      "content_score": "{Mean_Of_The_Three_Content_Criteria_One_Decimal}",
      "structure_score": "{Mean_Of_The_Three_Structure_Criteria_One_Decimal}",
      "overall_score": "{content_score_Plus_structure_score_One_Decimal}"
    },
    "B": { "...": "the same fields, scored independently" }
  },
  "output_quality": {
    "A": {
      "score": "{overall_score_Rounded_To_The_Nearest_Integer}",
      "strengths": ["{Observed_Strength_With_The_Detail_That_Evidences_It}"],
      "weaknesses": ["{Observed_Shortcoming_With_The_Detail_That_Evidences_It}"]
    },
    "B": { "...": "the same fields" }
  },
  "expectation_results": {
    "A": {
      "passed": "{Count_Satisfied}",
      "total": "{Count_Checked}",
      "pass_rate": "{passed_Divided_By_total_As_A_Fraction}",
      "details": [
        {"text": "{Expectation_Verbatim}", "passed": "{Boolean}"}
      ]
    },
    "B": { "...": "the same fields" }
  }
}
```

Scores are unquoted numbers in a real file. `task_specific` is omitted when the six fixed criteria
cover the task; `expectation_results` is omitted entirely when no expectations were supplied.

### `analysis.json`

Written by the analyzer in comparison mode, to the `output_path` it was given. Slots again, copied
from `agents/analyzer.md`.

```json
{
  "comparison_summary": {
    "winner": "A | B | TIE",
    "winner_skill": "{Path_You_Were_Given_For_The_Winning_Skill}",
    "loser_skill": "{Path_You_Were_Given_For_The_Losing_Skill}",
    "comparator_reasoning": "{One_Or_Two_Sentences_Restating_What_Decided_The_Comparison}"
  },
  "winner_strengths": [
    "{Specific_Feature_Of_The_Winning_Skill_And_The_Output_Difference_It_Produced}"
  ],
  "loser_weaknesses": [
    "{Quoted_Text_Or_Missing_Element_In_The_Losing_Skill_And_What_It_Cost}"
  ],
  "instruction_following": {
    "winner": {
      "score": "{1_To_10_From_The_Transcript}",
      "issues": ["{Departure_From_The_Skill_Visible_In_The_Transcript}"]
    },
    "loser": {
      "score": "{1_To_10_From_The_Transcript}",
      "issues": ["{Departure_From_The_Skill_Visible_In_The_Transcript}"]
    }
  },
  "improvement_suggestions": [
    {
      "priority": "high | medium | low",
      "category": "instructions | tools | examples | error_handling | structure | references",
      "suggestion": "{The_Concrete_Change_Including_The_Text_To_Replace_And_Its_Replacement}",
      "expected_impact": "{Which_Observed_Difference_This_Would_Have_Addressed}"
    }
  ],
  "transcript_insights": {
    "winner_execution_pattern": "{Sequence_Of_Steps_The_Winning_Run_Actually_Took}",
    "loser_execution_pattern": "{Sequence_Of_Steps_The_Losing_Run_Actually_Took}"
  }
}
```

`instruction_following` and `transcript_insights` are omitted entirely when no transcripts were
supplied — a score for behavior nobody observed is worse than no score.

**Who reads these:** `assignment_key.json` and `comparison.json` are read by you; the analyzer is
additionally given the comparator's file. No script reads any of the three.

**Checker:** no runtime validator writes or rejects these files. There is a **build-time** one:

```bash
python -m unittest tests.test_agent_prompt_contracts -v
```

It diffs the field names in `agents/*.md` against this document and against what the consumers
actually read, and it **executes** the de-identification block above — running `deidentify()` into a
temporary tree, comparing the `assignment_key.json` it really writes to the example in this section,
and replaying the recorded seed to confirm it reproduces the A/B mapping.

That check exists because `agents/` is the one part of the bundle no program reads. Nothing imported
it, nothing validated it, and this section had already drifted once — the audit fields were added to
the key file while the example here still showed two. Renaming a rubric criterion, adding a key, or
dropping one now fails a test that names the exact path, instead of surviving until someone reads
both files side by side.

---

## 10. Description optimization artifacts

### Trigger eval set

A top-level JSON **array**, exported by `assets/eval_review.html` (the "Export Eval Set" button) as
`eval_set.json`, and passed to `scripts.run_eval` / `scripts.run_loop` with `--eval-set`.

```json
[
  {"query": "{Realistic_User_Message_This_Skill_Should_Match}", "should_trigger": true},
  {"query": "{Second_Message_This_Skill_Should_Match}", "should_trigger": true},
  {"query": "{Realistic_User_Message_This_Skill_Should_Not_Match}", "should_trigger": false},
  {"query": "{Near_Miss_That_Sounds_Related_But_Is_Not}", "should_trigger": false}
]
```

**Fields**

- `query` — non-empty string. A realistic user message. Both readers index this key directly, so a
  missing one raises rather than silently defaulting.
- `should_trigger` — JSON boolean. Whether this skill's description should match that message.
- `id` — optional. `run_eval` copies it through onto each result record for correlation. The editor
  does not write it; hand-authored eval sets may.

Include negative queries. A set of only positives optimizes toward a description that fires on
everything.

### Optimizer result JSON

Printed to stdout by `python -m scripts.run_loop`, and written to `<results-dir>/results.json` when
`--results-dir` is given.

```json
{
  "exit_reason": "{Why_The_Loop_Stopped}",
  "original_description": "{The_Description_The_Loop_Started_From}",
  "best_description": "{The_Best_Scoring_Description}",
  "best_score": "1/2",
  "best_train_score": "1/2",
  "best_test_score": "1/2",
  "final_description": "{The_Description_The_Loop_Ended_On}",
  "iterations_run": 1,
  "holdout": 0.5,
  "train_size": 2,
  "test_size": 2,
  "history": [
    {
      "iteration": 1,
      "description": "{The_Description_Scored_In_This_Iteration}",
      "train_passed": 1,
      "train_failed": 1,
      "train_total": 2,
      "train_results": [
        {"query": "{Realistic_User_Message_This_Skill_Should_Match}", "should_trigger": true, "trigger_rate": 1.0, "triggers": 2, "runs": 2, "pass": true},
        {"query": "{Realistic_User_Message_This_Skill_Should_Not_Match}", "should_trigger": false, "trigger_rate": 1.0, "triggers": 2, "runs": 2, "pass": false}
      ],
      "test_passed": 1,
      "test_failed": 1,
      "test_total": 2,
      "test_results": [
        {"query": "{Second_Message_This_Skill_Should_Match}", "should_trigger": true, "trigger_rate": 0.0, "triggers": 0, "runs": 2, "pass": false},
        {"query": "{Near_Miss_That_Sounds_Related_But_Is_Not}", "should_trigger": false, "trigger_rate": 0.0, "triggers": 0, "runs": 2, "pass": true}
      ]
    }
  ]
}
```

**Fields**

- `original_description` / `best_description` / `final_description` — the starting text, the
  best-scoring text, and the text the loop ended on. `best_description` is the one to apply.
- `best_score` / `best_train_score` / `best_test_score` — `"passed/total"` strings.
  `best_test_score` is `null` when `--holdout 0` disabled the split.
- `exit_reason` — why the loop stopped, as one of `all_passed`, `max_iterations`,
  `all_queries_errored` or `improve_failed`, each followed by the iteration or limit in parentheses.
  It is a display string, not an enum a consumer branches on.
- `iterations_run`, `holdout`, `train_size`, `test_size` — the run's shape.
- `history[]` — one entry per iteration.
  - `iteration` — integer, 1-based.
  - `description` — the text scored in that iteration.
  - `train_passed` / `train_failed` / `train_total`, and `test_*` — integers; the `test_*` fields are
    `null` when there is no holdout.
  - `train_results[]` / `test_results[]` — one record per query, as `run_eval` returns them. The
    report reads `query`, `should_trigger`, `trigger_rate`, `triggers`, `runs` and `pass` from each;
    `run_eval` emits further fields alongside those, including an error count and a per-query
    `status`, and a query whose probes all errored is scored as no verdict rather than as a
    non-trigger.

The test set is blinded before each improvement step: every `test_`-prefixed key is stripped from the
history handed to the improver, so it cannot optimize against the holdout.

**Who reads it:** `scripts/generate_report.py`, which renders the HTML report, and
`scripts/improve_description.py`, which reads the history to write the next candidate.

**Checker:** none, but the shape above was run through `generate_report.generate_html()` — the actual
consumer — and rendered without error.

---

## 11. `assertions` vs `expectations`

The same list of verifiable statements is called two different things on purpose, and the two words do
not substitute for each other:

| Word | Where | What it is |
|---|---|---|
| `assertions` | `evals/evals.json`, `eval_metadata.json` | the **input** set an author writes |
| `expectations` | `grading.json`, `benchmark.json`, the comparator's `expectations` input | the **graded** results a grader returns |

`assertions` are strings. `expectations` are objects, one per assertion, carrying `text`, `passed`
and `evidence`. The text inside an `expectation` is the assertion copied character-for-character.

The validator flags both mistakes by name: an `assertions` key in `grading.json`, and an
`expectations` key in `eval_metadata.json`.

---

## 12. What is checked, and what is not

Two different kinds of check, and it matters which one you have. A **runtime** checker inspects the
file you just produced and can stop the run. A **build-time** check compares the *schemas* — this
document, `agents/*.md`, and what the consumers read — and catches drift in the bundle itself, not in
your workspace.

| File | Runtime check | Build-time check |
|---|---|---|
| `grading.json` | `python -m scripts.validate_grading <path> [--json]` | field names vs `agents/grader.md`; required-vs-omittable blocks probed |
| `timing.json` | same command; validated as a sibling of each `grading.json` | — |
| `eval_metadata.json` | same command; validated per eval directory | — |
| workspace layout | same command; unreachable files are errors, legacy-flat is a warning | — |
| `benchmark.json` / `benchmark.md` | **none** — written by `scripts.aggregate_benchmark`, not validated after the fact | top-level keys and `runs[].result` vs the aggregator and vs `agents/analyzer.md` |
| `assignment_key.json` | **none** | `deidentify()` executed; written keys vs this document; seed replayed |
| `comparison.json` / `analysis.json` | **none** | key trees vs `agents/comparator.md` and `agents/analyzer.md` |
| `evals/evals.json` | **none** | — |
| `feedback.json` | **none** — the POST handler requires a `reviews` key and nothing more | — |
| trigger eval set | **none** — readers index `query` and `should_trigger` directly, so a malformed set raises | — |
| optimizer `results.json` | **none** | — |

### What a non-zero exit means

`scripts.aggregate_benchmark` distinguishes two kinds of error-severity condition, and the
distinction is the whole exit-code contract:

| Condition | Exit | Why |
|---|---|---|
| **Visible in the artifact** — a `grading.json` or `timing.json` that failed schema validation, excluded and listed in `exclusions` with the validator's messages | **0** | The benchmark is still trustworthy over what remains, and it reports its own gaps. The exclusion speaks for itself. |
| **Makes the artifact unsound** — zero discovered runs, graded runs no reader can see, or a delta whose two sides did not run the same evals | **1** | The number a reader would take away is wrong, and nothing in the artifact would tell them. |

So a green exit does not mean nothing was dropped — it means everything dropped is written down.
Read `exclusions` even on exit 0. A red exit means do not use the delta at all.

The build-time column is one command:

```bash
python -m unittest tests.test_agent_prompt_contracts -v
```

It covers field names and nesting, not prose. A sentence in this document can still contradict the
mechanism it describes without failing anything — which is exactly how the analyst-notes paragraph in
[§7](#7-benchmarkjson-and-benchmarkmd) went stale. When you change a shape, change it in the prompt,
here, and in the consumer, then run that command.

`--json` sends the machine-readable report to stdout alone; every human-readable line goes to stderr,
so a machine consumer is never corrupted by progress chatter.

Run the validator before aggregating, not after. The failure it exists to catch does not raise on its
own — it produces a clean, plausible, wrong number.

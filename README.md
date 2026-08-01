# better-skill-creator

A skill for building Claude skills — and for finding out whether the one you built actually helps.

This is a substantially rewritten derivative of the `skill-creator` skill from
[anthropics/skills](https://github.com/anthropics/skills), under Apache-2.0. It is **not affiliated
with or endorsed by Anthropic**; please don't send them issues about it. See [NOTICE](NOTICE).

---

## Why this exists

The original is a good design. Its evaluation loop — run your skill against real prompts, run a
baseline alongside it, put both in front of a human before you start rewriting — is the right shape,
and this project keeps it.

What it had was a class of bug that matters more here than almost anywhere else: **the measurements
could be wrong without saying so.**

An authoring tool is only worth using if you can trust what it tells you. These were all reproducible
before the rewrite:

- A workspace laid out exactly as the documentation specified aggregated to `Delta: +0.00` — a
  complete, plausible benchmark table computed from **zero discovered runs**, exit code 0. The two
  runs it ignored had both graded 100%.
- In the "is my new version better?" path, configurations were ordered alphabetically, so `old_skill`
  became the baseline's baseline. A genuine improvement from 23% to 92% rendered as **`-0.68`**.
- The trigger-rate evaluator used `select()` on a pipe, which is illegal on Windows. Every probe
  raised, every exception was swallowed into "did not trigger," and the result was well-formed JSON in
  which every positive failed and every negative passed — then fed to an optimizer that rewrote your
  description five times based on it.
- The frontmatter validator enforced one key set as universal and **rejected 23 of the 30 first-party
  skills** installed on the test machine, all from Anthropic's own marketplace.
- The packager shipped `.env` files, `.git/`, and symlink targets from outside the source tree into
  the archive you hand to other people.
- The "Tokens" column reported character counts — 84,852 displayed as 12,450.
- `SKILL.md` was 38,348 characters against a ~19,900-character post-compaction slice, so **48% of it
  silently vanished** at exactly the point a long session needed it — starting with the section the
  file itself called "the heart of the loop."

None of these crash. Every one produces a confident, well-formatted answer.

## What changed

**Measurements refuse instead of guessing.** Zero discovered runs is now a non-zero exit that prints
every path searched. Unmeasured values render `—`, never `0`. A probe that errored is recorded as an
error and excluded from the denominator, not counted as a clean negative.

**One canonical workspace layout**, agreed on by the workflow, the aggregator, the viewer, and the
grading validator — which previously disagreed with each other in ways that produced silent zeros.
Plus `scripts/preflight.py`, which checks the layout *before* you spend anything on sub-agent runs.

**Target-aware validation.** There is no single frontmatter spec: Claude Code recognizes 31 keys and
ignores unknown ones, the portable agentskills.io set is 6, and claude.ai caps descriptions at 200
characters where Claude Code allows 1024. `quick_validate` takes `--target` and names which one
produced each finding.

**Cross-platform file I/O throughout.** ~30 call sites read and wrote at the platform default
encoding, which on Windows corrupted skill descriptions silently and crashed several entry points
outright.

**Spend controls and probe isolation.** The description optimizer projects its cost before starting
and refuses past `--max-cost`. Each probe runs in its own temporary project root — the previous
version wrote into whatever `.claude/` directory it found by walking upward, which could be your
project, your home directory, or a drive root.

**Rewritten prompts and documentation.** `SKILL.md` is 18,870 characters and survives compaction
whole. Six reference files carry the detail, loaded on demand. The sub-agent prompts no longer ship
worked examples containing finished verdicts, and the blind comparator's blinding is now performed by
a de-identification step rather than asserted in a sentence.

**Validated in a clean room.** See [VALIDATION.md](VALIDATION.md) — 13/13 on held-out ground built by agents who never saw the panel, key-verified by a second blind reader, against a 46% baseline. The panel beat every seat that composed it.

**A test suite**, most of it derived from the reproductions above — each fixture is a defect that
actually happened. Run `python -m unittest discover tests` to see the current count.

## Install

A skill is a directory. Copy it where Claude looks:

```bash
git clone https://github.com/<owner>/better-skill-creator
cp -r better-skill-creator ~/.claude/skills/better-skill-creator      # personal
cp -r better-skill-creator .claude/skills/better-skill-creator        # this project
```

Claude Code picks it up live — no restart. Then just describe what you want:

> "I keep writing the same kind of release notes by hand. Can we make Claude do it the way I do it?"

**Note on the name.** The repository, the directory you install it as, and the frontmatter `name` are
all `better-skill-creator`. Claude Code takes a skill's invocation name from its **directory**, so
holding all three in agreement is what makes it answer to the name its own file states.

Two consequences worth knowing:

- This does **not** shadow Anthropic's `skill-creator`. Install both and both stay available, each
  under its own name. If you would rather this one take that name over, install it into a directory
  called `skill-creator` **and** change the frontmatter `name` to match. Changing only one of them
  gets you a skill that answers to a name its own file doesn't state.
- `package_skill` refuses to build an archive when the directory and the frontmatter `name` disagree.
  They agree here, so you can package straight from the clone root.

## Requirements

- Python 3.10+ and PyYAML (`pip install -r requirements.txt`)
- The `claude` CLI, for description-triggering optimization only — everything else works without it

## Running the tests

```bash
python -m unittest discover tests
```

## Contributing

Bug reports are most useful with a reproduction. If a measurement looked right and wasn't, that is the
highest-priority category of issue here.

## License

Apache-2.0. See [LICENSE.txt](LICENSE.txt) and [NOTICE](NOTICE).

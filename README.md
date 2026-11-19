# guardscore

**Real incidents. Fair scores.**

## The problem

AI coding agents sometimes take actions that cannot be undone. An agent fixing a credential issue might call a cloud API that deletes a production database and all its backups. An agent told to clean up old files might also wipe a home directory. These things have happened.

People build "guards" to catch these actions before they run. A guard might block a command outright, or pause and ask a human. The trouble is that every guard author tests on their own small set of cases and reports their own score. There is no shared baseline, so the numbers are not comparable.

guardscore is that baseline. It is a collection of real incidents turned into replayable test cases, plus a runner and scoreboard that any guard can be measured against. Every case comes from a documented public event. Every score is reproducible.

## What is here now

Phase 1 built the case library:

- A defined case format (see [docs/case-format.md](docs/case-format.md))
- A loader and validator for TOML case files
- Command-line tools to validate cases and print statistics
- The first real incident cases, each traced to a public source
- Everyday cases: safe, routine commands that a guard should let through

Phase 2 adds the runner. It shows every case to a guard, records the answer, and scores it. No third-party guard has been scored yet. The only guards measured so far are the four built-in baselines, which exist as a sanity floor, not as a recommendation for how a real guard should work.

## Quickstart

```
pip install -e ".[dev]"
python -m guardscore validate
python -m guardscore stats
```

## Running the baselines

```
python -m guardscore run --guard builtin:allow-all --guard builtin:block-all --guard builtin:coin-flip --guard builtin:naive-patterns
```

To plug in your own guard, see [docs/guards.md](docs/guards.md) for the spec syntax (plain Python functions, any command, or a Claude Code hook script). To understand what the numbers mean, see [docs/scoring.md](docs/scoring.md).

## Project layout

```
cases/incidents/   Real incidents that a guard should block
cases/everyday/    Routine commands that a guard should allow
src/guardscore/    Python package: loader, validator, CLI
docs/              Documentation
tests/             Test suite
```

## What is in the case library

```
Total cases: 31

Scorable: 29
Not scorable: 2

By kind:
  everyday: 18
  incident: 13

By expected verdict:
  allow: 18
  hold: 13

By outcome:
  harm: 9
  no_harm: 3
  unclear: 1

By occurrence:
  demonstration: 2
  in_the_wild: 11

By tag:
  everyday: 18
  destructive: 13
  filesystem: 11
  lookalike: 10
  git: 8
  cloud-cli: 5
  prompt-injection: 3
  database: 2
  cloud-api: 2
  network: 1
  credentials: 1
```

Run `python -m guardscore stats` to see the current numbers.

## Baseline scores

These are the four built-in baselines. Two incident cases have action text that looks routine on its face, with the harm coming from hidden state rather than the command itself, so they are marked not scorable and left out of every count below. That leaves 29 scorable cases: 11 incidents and 18 everyday cases. Latency is left out here because it depends on the machine it runs on. Run the command above yourself to see timing on your own machine.

| Guard | Judged | Caught | Caught (literal) | Caught (reconstructed) | Wrongly held | Balanced | Errors | Not scorable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| builtin:naive-patterns | 29 | 4 of 11 | 2 of 4 (fewer than 5 cases) | 2 of 7 | 2 of 18 | 63% | 0 | 2 |
| builtin:coin-flip | 29 | 6 of 11 | 3 of 4 (fewer than 5 cases) | 3 of 7 | 7 of 18 | 58% | 0 | 2 |
| builtin:allow-all | 29 | 0 of 11 | 0 of 4 (fewer than 5 cases) | 0 of 7 | 0 of 18 | 50% | 0 | 2 |
| builtin:block-all | 29 | 11 of 11 | 4 of 4 (fewer than 5 cases) | 7 of 7 | 18 of 18 | 50% | 0 | 2 |

naive-patterns is not an independent measure. Its pattern categories were chosen by this project, and some overlap with commands that appear in the shipped incidents, so its score here is not a bar for other guards to clear. It is a sanity floor that shows the scoring machinery works, nothing more.

As cases were added during this phase, the naive-patterns baseline moved from 80% to 63% balanced, with no change at all to its patterns. The regex rules have not been touched since the commit that first added them. A small, hand-picked case set can swing a lot just from adding a few new cases, which is itself a reason to read any single balanced score here as a rough signal rather than a fixed fact about a guard.

7 of the 11 scorable incident cases use reconstructed action text, meaning the exact command was not published and this project wrote a plausible stand in. The table splits the catch count into literal and reconstructed cases for this reason: a guard that misses a reconstructed case may be reacting to how that text was written rather than to the real incident, so a miss there is weaker evidence than a miss on a literal case. Both groups here are small enough that the table marks them as having fewer than 5 cases, which is a reminder to read the split as a rough signal, not a settled number. See [docs/scoring.md](docs/scoring.md) for what each column means, why the two trivial baselines both land at 50 percent, and more on what reconstructed text does and does not tell you.

## Limits of this project, honestly

- 13 incidents is a small sample, and 2 of them have action text that only looks safe because the real harm came from hidden state, not from the command itself, so they are marked not scorable and left out of every score. That leaves 11 scorable incidents, of which 4 use the literal command from a source and 7 use a reconstructed stand in. Treat every score here as a rough floor, not a certified ranking.
- Of the 13 incidents, 11 are marked as having happened to a real user or in a real release, and 2 are marked as a researcher's or vendor's own demonstration rather than a real-world event. See the `occurrence` field in [docs/case-format.md](docs/case-format.md) for what each label means.
- The cases lean toward coding agents and shell commands. A guard built for a different kind of agent or a different tool surface may score differently than these numbers suggest.
- The baselines are sanity floors written by this project. They are not rivals to real guards and not a recommendation for how to build one.
- Nothing here proves that a real AI agent would ever attempt any of these actions, or that a guard would actually stop it in a live session. This only measures whether a guard holds an action when it is shown that action directly.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add an incident case.

## License

MIT. See [LICENSE](LICENSE).

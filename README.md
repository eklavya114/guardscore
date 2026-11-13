# guardscore

**Real incidents. Fair scores.**

## The problem

AI coding agents sometimes take actions that cannot be undone. An agent fixing a credential issue might call a cloud API that deletes a production database and all its backups. An agent told to clean up old files might also wipe a home directory. These things have happened.

People build "guards" to catch these actions before they run. A guard might block a command outright, or pause and ask a human. The trouble is that every guard author tests on their own small set of cases and reports their own score. There is no shared baseline, so the numbers are not comparable.

guardscore is that baseline. It is a collection of real incidents turned into replayable test cases, plus a runner and scoreboard that any guard can be measured against. Every case comes from a documented public event. Every score is reproducible.

## What is here now (Phase 1)

Phase 1 builds the foundation:

- A defined case format (see [docs/case-format.md](docs/case-format.md))
- A loader and validator for TOML case files
- Command-line tools to validate cases and print statistics
- The first real incident cases, each traced to a public source
- Everyday cases: safe, routine commands that a guard should let through

There is no runner yet. Phase 1 is the case library and the tooling to keep it honest. The runner, scoring, and leaderboard come in later phases.

## Quickstart

```
pip install -e ".[dev]"
python -m guardscore validate
python -m guardscore stats
```

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
Total cases: 14

By kind:
  everyday: 8
  incident: 6

By expected verdict:
  allow: 8
  hold: 6

By tag:
  everyday: 8
  destructive: 6
  filesystem: 5
  git: 5
  prompt-injection: 1
  cloud-cli: 1
  cloud-api: 1
  credentials: 1
  database: 1
```

Run `python -m guardscore stats` to see the current numbers.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add an incident case.

## License

MIT. See [LICENSE](LICENSE).

# Contributing

Use a focused pull request and explain the observable behavior, validation and
limits. Do not include household configuration, tokens, device identifiers,
recordings, recovery images or trained personal models. Read [SECURITY.md](SECURITY.md)
for private reporting. The project follows upstream licenses and does not
redistribute Amazon firmware.

## Development checks

Use Python 3.11 for repository tooling. Install the locked test dependencies in
an isolated virtual environment; dependencies of Home Assistant integration tests
come from the pinned HA image in CI.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python scripts/check_docs.py
.venv/bin/python scripts/check_public.py --include-untracked
```

The public-source audit checks the Git index and working files. Stage only the
intended public files and run it again before committing. It complements review;
it cannot certify that every possible secret is absent. Do not run runtime tests
inside the live Home Assistant server process. CI executes `runtime_*.py` in an
isolated container without network access; see [CI](docs/ci.md).

## Documentation and translations

`README.md` is the English project overview. `README.ru.md`, `README.de.md`,
`README.es.md` and `README.fr.md` cover the same prerequisites, steps and limits.
Operational runbooks remain canonical English sources. Translations must never
claim that a localized guide proves microphone, STT or TTS support.

When changing setup steps or a supported capability, update every affected
README, [the language inventory](docs/languages.json), related runbooks and
[i18n documentation](docs/i18n.md) in the same PR. Keep command names, entity IDs,
paths and actual phrases to speak unchanged unless their behavior changes.
Locale fallback and integration translations have separate executable tests.

Use descriptive links, meaningful image alt text and accessible SVGs with a
`title`, `desc` and `viewBox`. Avoid external fonts, scripts and embedded
household screenshots. The [diagram notes](docs/assets/README.md) state the data
behind each chart. Never fill missing measurements with guessed values.

## Publication and review

[Shared CI](docs/ci.md) must pass. Resolve substantive review findings before
merging; do not disable checks or rely on approval of an older commit. Render
[the wiki](docs/wiki.md) from the reviewed source revision. Review changes to a
wiki checkout before pushing, preserving pages this exporter does not own.
Documentation changes do not authorize a firmware upgrade or modification of
live household devices.

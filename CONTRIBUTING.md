# Contributing

This repository is developed in the open: fork it, branch, open a pull
request. No CLA, no template to sign.

## Where your issue belongs

This package is a thin client: `mode="api"` posts your document to the hosted
Attestwire API, and `mode="cli"` shells out to
[`@attestwire/en16931`](https://github.com/attestwire/en16931). It contains no
validation logic of its own.

So:

- A rule that fired when it shouldn't have, or a finding whose message/fix
  text is wrong — that's the engine (`mode="cli"`) or the hosted API
  (`mode="api"`). Report an engine issue at
  [attestwire/en16931](https://github.com/attestwire/en16931/issues).
- The Python API itself — `validate()`'s signature, how `ValidationResult` /
  `Finding` / `Location` model the JSON, error handling, the `factur-x` /
  `python-drafthorse` recipes — that's here.

## Running the tests

Python 3.9+, standard library only.

```bash
python3 -m unittest discover -v
```

Every test mocks `urllib.request.urlopen` (`tests/test_api.py`) or
`subprocess.run` (`tests/test_cli.py`) — no network access and no Node.js
needed to run the suite. `tests/test_live.py` is opt-in and skipped by
default; see its module docstring.

## Before you open the PR

Run `python3 -m unittest discover -v`. If you touch the API or CLI request
shape, check it against the published contract
(https://api.attestwire.com/openapi.json) /
the engine's command line (`npx @attestwire/en16931 --help`, source at
[attestwire/en16931](https://github.com/attestwire/en16931)) rather than guessing —
this package's whole job is matching that contract exactly.

## Questions

Open an issue, or email hello@attestwire.com.

Security issues go to hello@attestwire.com. See [SECURITY.md](SECURITY.md).

## Licence

MIT. By contributing, you agree your contribution ships under it.

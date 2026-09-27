# Changelog

## [Unreleased]

- Initial release: `validate(data, *, api_key=None, mode="api")`, with `mode="api"`
  (`POST /v1/validate` on the hosted Attestwire API) and `mode="cli"` (local
  `npx @attestwire/en16931 --json`) backends, a typed `ValidationResult` /
  `Finding` / `Location`, and documented recipes for akretion's `factur-x` and
  pretix's `python-drafthorse`.

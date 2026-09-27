# Security

## Reporting

Email **hello@attestwire.com**. The maintainer reads these directly.

Include what you found, how to reproduce it, and the package version you were
on. Please don't open a public issue for a security report.

There's no bug bounty. If you'd like credit, say so and you'll be named in
the release notes for the fix.

## Scope

This package sends invoice documents — which carry customer names, addresses,
VAT IDs and bank details — either to the hosted Attestwire API (`mode="api"`)
or to a local Node process (`mode="cli"`), and handles your API key in the
former case. Worth reporting:

- Anything that sends your document or API key somewhere other than the
  `origin` you configured (default `https://api.attestwire.com`).
- A temp file `mode="cli"` writes that is not cleaned up, or that is created
  with permissions wider than the current user.
- Anything that logs a document's contents or your API key.
- Command injection through `node_command` / `package_spec` — both are passed
  as separate `subprocess.run()` argv elements, never through a shell; a PR
  that changes that needs a very good reason.

## Out of scope

A wrong verdict, or malformed XML from the engine, is a bug in the rule
engine. Report it at
[attestwire/en16931](https://github.com/attestwire/en16931/issues).
Vulnerabilities in the engine itself (XML parsing, entity expansion, the PDF
reader) belong in that repository's
[SECURITY.md](https://github.com/attestwire/en16931/blob/main/SECURITY.md)
process, same email either way.

Vulnerabilities in the hosted Attestwire API (`api.attestwire.com`) go to
Attestwire directly, not this repository.

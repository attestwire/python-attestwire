"""``mode="cli"``: run ``npx --yes @attestwire/en16931 --json <tmpfile>`` locally.

Nothing is uploaded anywhere — this shells out to Node (which `npx` fetches
and caches on first use if it is not already installed) and reads its
``--json`` output from stdout. Needs Node.js/npm on `PATH`. See
``src/cli.ts` in github.com/attestwire/en16931` for exactly what that command prints: a
top-level ``results`` array, one entry per file given (here, always exactly
one — the temp file this writes), each with ``findings`` in the same
``TeachingError`` shape the hosted API uses, plus ``passed``.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Optional

from ._detect import suffix_for
from ._exceptions import CliError
from ._types import Finding, ValidationResult

DEFAULT_NODE_COMMAND = "npx"
DEFAULT_PACKAGE_SPEC = "@attestwire/en16931"


def validate_via_cli(
    data: bytes,
    *,
    node_command: str = DEFAULT_NODE_COMMAND,
    package_spec: str = DEFAULT_PACKAGE_SPEC,
    timeout: float = 120.0,
) -> ValidationResult:
    fd, tmp_path = tempfile.mkstemp(suffix=suffix_for(data))
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(data)

        try:
            completed = subprocess.run(
                [node_command, "--yes", package_spec, "--json", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise CliError(
                f'"{node_command}" was not found on PATH. mode="cli" needs Node.js '
                f'(npx comes with it) to run `npx --yes {package_spec}`. Install Node from '
                'https://nodejs.org, pass node_command= to point at it explicitly, or use '
                'mode="api" instead.'
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CliError(
                f"`{node_command} --yes {package_spec} --json {tmp_path}` did not finish "
                f"within {timeout}s. The first run downloads the package via npm and can be "
                "slow on a cold cache; try again, or raise timeout=."
            ) from exc

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            stderr = completed.stderr.strip()
            raise CliError(
                f"`{node_command} --yes {package_spec} --json` did not print JSON on stdout "
                f"(exit code {completed.returncode}). This is usually npm/npx failing before "
                "the validator ran (no network to fetch the package, no matching Node "
                f"version, ...).\nstderr:\n{stderr}"
            ) from exc

        results = payload.get("results") or []
        if not results:
            raise CliError(
                f"`{node_command} --yes {package_spec} --json` returned no results for "
                f"{tmp_path!r}: {payload!r}"
            )
        result = results[0]
        findings = [Finding.from_json(f) for f in result.get("findings") or []]
        return ValidationResult(
            valid=bool(result.get("passed")),
            findings=findings,
            mode="cli",
            profile=result.get("profile"),
            syntax=result.get("syntax"),
            container=result.get("container"),
            source=None,
            raw=payload,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

# Security and private data

This repository contains deployment tooling and an optional Home Assistant
integration. Upstream EchoMuse, emOS, Home Assistant and speech providers have
separate release and security policies. Follow their advisories as well.

## Report privately

For a vulnerability, use [GitHub private reporting](https://github.com/ha-homelab/ha-echomuse/security/advisories/new)
or email **alvit.work@gmail.com**. Do not post credentials, device dumps or
household data in public issues.

Include the affected commit, component, a minimal sanitized reproduction and
impact. Use documentation addresses and placeholders, not live network details.
Do not upload Amazon firmware or personal voice recordings.

## Operational boundaries

- Keep device credentials, controller state, recovery backups and recordings
  outside the public repository; examples contain placeholders only.
- Use the documented TLS and authentication paths. Treat root Console access as
  administrative access to the device; avoid exposing management services publicly.
- Home tools are restricted to the local Ollama agent. Keep household facts and
  controls out of optional public general-question providers.
- A local model does not make cloud STT local. Review each speech stage and
  provider before selecting a pipeline.
- Controls require an explicit allowlist and HA permissions. Do not expand it to
  unrelated entities to work around a failed command.

[Access](docs/device-access.md), [home tools](docs/home-control.md),
[operations](docs/operations.md) and [public-source checks](CONTRIBUTING.md)
explain the corresponding setup and validation.


## Response and supported source

The current main-branch tools and latest 0.3 integration source receive security
fixes. Include the exact Git revision and integration version with a report.
The maintainer aims to acknowledge within 14 days, reproduce privately, assess
impact, test the fix and coordinate disclosure. Critical vulnerabilities are
addressed immediately; other medium-or-higher findings should be fixed within
60 days. Release notes include available CVE/GHSA identifiers and reporter credit
unless anonymity is requested. Retry the alternative private contact if needed.
There is no independent security team or backup maintainer.

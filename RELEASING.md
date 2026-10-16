# Source versions and validation

The full Git commit SHA identifies every public source revision. Download the
commit-specific archive from GitHub over HTTPS and record its SHA; never disable
certificate validation. Branch archives change over time. Existing named versions
and human-readable changes are in [CHANGELOG.md](CHANGELOG.md). An untagged
revision is a development snapshot, not an invented stable firmware release.

Before release, review changes, dependency/security findings, compatibility,
license notices, and passing required CI. Run the documented development checks:

```sh
python3 -m unittest discover -s tests -p "test_*.py"
python3 scripts/check_docs.py
python3 scripts/check_public.py --include-untracked
```

Use a reviewed PR for code, dependency or packaging changes and publish
human-readable notes including known security fixes, relevant CVE/GHSA IDs and
upgrade guidance. Preserve previous source versions; do not rewrite published
release identity. A signed, byte-for-byte reproducible artifact process is not
claimed by this document.

Installation and operating requirements are in [README.md](README.md). Preserve
private configuration before updating. For rollback, use a previously reviewed
source revision compatible with the current configuration. Repository tests and
compiler results do not replace target hardware/OS acceptance. A stable binary
release requires recorded tests of the exact candidate on its intended targets;
no physical deployment or flashing occurs in CI.

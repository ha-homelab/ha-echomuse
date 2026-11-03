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

## EchoMuse Home Tools beta package

The component version in `custom_components/echomuse_home/manifest.json` is
separate from repository source snapshots and upstream device firmware. Use a
reviewed version PR and completed required CI before tagging
`echomuse-home-v<version>` as a prerelease on its full source commit.

Retain the established package contract: `echomuse_home-<version>.zip`,
`release-manifest.json` and `SHA256SUMS.txt`. The ZIP contains only the committed
`custom_components/echomuse_home/` files, the repository license, an `INSTALL.md`
with version-specific installation and rollback instructions, and `SOURCE.json`
with the exact repository, commit and version. The release manifest records each
payload file's size/hash, the ZIP size/hash and the actual qualification scope.
Generate these files from committed Git objects, never a running installation
or an untracked working directory. Download the published assets and compare
all bytes and source references before announcing completion.

The package is the full public integration. A successful targeted patch of an
older customized installation does not qualify that installation as the full
package. Describe that difference, the tested HA versions and any remaining
physical acceptance limits in the notes. Publication does not restart or update
Home Assistant. Retain the previous package and configuration for operator-led
rollback; never rewrite an existing release tag or asset.

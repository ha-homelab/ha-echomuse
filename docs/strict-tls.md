# Strict artifact-download transport

`scripts/fetch_upstream.py --strict-tls` requires OpenSSL 3 and preserves normal
certificate/hostname verification with TLS 1.2 or newer and security level at
least 3. RSA/DH keys below 3072 bits, EC keys below 256 bits and static RSA
exchange are rejected. Stronger host policy and existing cipher restrictions
are preserved. Every accepted redirect remains HTTPS on the GitHub release-host
allowlist and uses the same handler. There is no plaintext fallback.

The optional profile may reject a server certificate chain accepted by ordinary
TLS; this is an explicit interoperability choice. Standard OpenSSL trust settings
can supply a trusted CA, but the full chain must meet the profile. Downloaded
artifacts still require exact pinned size and SHA-256 and are never executed by
the downloader. No account password or token is required for these public files.

Synthetic in-memory TLS tests verify strong chains, weak root/intermediate/leaf
rejection, trust and hostname failures in TLS 1.2 and 1.3. A downloader test checks
that its HTTPS handler carries this verified policy. These tests do not download
or execute upstream firmware. The Home Assistant integration calls HA APIs in
process; HA's own listener and authentication policy remain administrator-owned.

# Strict artifact-download transport

`scripts/fetch_upstream.py --strict-tls` requires CPython 3.11 or newer and
OpenSSL 3. On Linux or Apple silicon macOS, install the hash-locked
development requirements first. These include cryptography and the synthetic
fixture test dependencies:

```sh
python -m pip install --require-hashes -r requirements-dev.txt
python scripts/fetch_upstream.py --strict-tls
```

The profile preserves normal certificate/hostname verification, requires TLS
1.2 or newer, and checks **every certificate in the verified chain**, including
the trust anchor, before sending HTTP data. RSA moduli must contain at least
2048 bits; EC keys at least 224 bits; DSA parameters at least 2048/224 bits.
Ed25519 and Ed448 are accepted. Unknown key algorithms or runtimes that cannot
expose a verified chain fail closed. OpenSSL security level 2 supplies the
112-bit algorithm floor; the additional exact key checks reject a 2047-bit RSA
modulus even when OpenSSL rounds it into that security level. Stronger host
policy and existing cipher restrictions are preserved.

Certificate metadata normally uses `cryptography`. On Intel macOS, the native
Security framework reads RSA/EC key metadata; it does not replace OpenSSL trust
verification, and unknown algorithms are rejected. The strict profile does not
require `cryptography` on that platform, so Intel runtime-only users skip the
requirements installation above and run the standard-library download command
directly. The current fixture requirements include cryptography and are qualified
on Linux and Apple silicon macOS; they are not an Intel installation recipe.
The native metadata implementation has been calibrated on Apple silicon with
exact RSA2047 rejection and RSA2048 acceptance. That does not establish a full
Intel runtime qualification, which remains pending.
The native helper and policy are MIT
adaptations credited in [third-party notices](../THIRD_PARTY_NOTICES.md).

Every accepted redirect remains HTTPS on the GitHub release-host allowlist and
uses the same verified handler. There is no plaintext fallback. Standard
OpenSSL trust settings can supply a trusted CA, but every key in its chain must
meet the profile. Both locked public EchoMuse artifacts were fetched using this
profile on 2026-10-16 with their exact sizes and SHA-256 values verified; they
were not executed. Downloaded files still require the pinned size and SHA-256,
and no account password or token is required for these public files.

Synthetic TLS tests cover exact RSA 2048-bit acceptance and 2047-bit rejection
at root/intermediate/leaf positions in TLS 1.2 and 1.3, plus trust and hostname
failures. They exercise both memory BIO and socket handshakes; the downloader
wiring test checks that its HTTPS handler carries the verified policy. The
Home Assistant integration calls HA APIs in process; HA's own listener and
authentication policy remain administrator-owned.

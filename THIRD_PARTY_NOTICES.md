# Third-party notices

The optional wake-word training workflow downloads frozen models and feature
data from [openWakeWord](https://github.com/dscripka/openWakeWord) and
[davidscripka/openwakeword_features](https://huggingface.co/datasets/davidscripka/openwakeword_features).
The feature dataset is CC BY-NC-SA 4.0; its terms are separate from this
repository's code license. It includes derived features from ACAV100M, DiPCo,
the Santa Barbara Corpus and MUSDB. Held-out raw speech comes from
[LibriSpeech / OpenSLR 12](https://www.openslr.org/12), CC BY 4.0. Existing Piper
voice provenance remains in the private input manifest. No downloaded weights,
personal models, recordings or derived voice features are bundled here.

The exact certificate-key guard in `scripts/tls_key_policy.py` and native macOS
metadata helper in `scripts/_darwin_certificate.py` adapt the MIT-licensed
[google-home-voice-stats TLS policy](https://github.com/4alvit/google-home-voice-stats/tree/4cbd3296bd08c515198136cb9480e3a6ba734768/igw_google_voice),
which credits the original victron-venus implementation. Their notices follow.
The separately downloaded EchoMuse artifacts retain their upstream licenses;
this repository does not relicense them.

```text
MIT License

Copyright (c) 2026 victron-venus
Copyright (c) 2026 alvit

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## EchoMuse Bluetooth authentication patch

`patches/echomuse-2.26.0/ble-auth-lifecycle.patch` contains modifications to
[EchoMuse 2.26.0](https://github.com/wilbowes/EchoMuse/tree/e119433c0845dfe80f4b1ec44c9e8e8028adbb07),
copyright (c) 2026 Wil Bowes, distributed under the MIT license. The complete
upstream notice is preserved in
[LICENSE-EchoMuse-MIT.txt](patches/echomuse-2.26.0/LICENSE-EchoMuse-MIT.txt).
The patch, its source/hash manifest, and tests do not include device data,
controller databases, pairing keys, or firmware images.

# Fixed-model local creative server

`scripts/local_family_server.py` provides a small authenticated endpoint for
the optional local family-generation route. It does not expose MLX-LM's model
management server. Reading the bundled poems and using the riddles do not need
this service.

The implementation can be tested without importing MLX, loading a model or
opening a listener. Passing those tests does not establish a model's Russian
creative quality or speed. Approve those separately before deployment.

## Runtime and model

Use CPython 3.12 on Apple Silicon and the separately pinned
[`requirements-local-family.txt`](../requirements-local-family.txt). The pins
record the reviewed environment, including `mlx-lm 0.32.2`, `mlx 0.32.4` and
`mlx-metal 0.32.4`; they are separate from the ordinary repository test stack.

The candidate model is [Qwen3-14B 4-bit](https://huggingface.co/mlx-community/Qwen3-14B-4bit/tree/a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4),
pinned to revision `a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4`. The
[model manifest](../examples/local-family-model.json) lists the required files,
expected sizes and upstream LFS checksums. Download that exact revision into
private storage and verify the large-file SHA-256 values before loading. The
complete listed payload is about 8.32 GB; it is not committed to this repository.

Provide an **absolute path** to already downloaded and independently verified
model files. Startup loads that one directory with `trust_remote_code=False`,
local-only tokenizer loading, Hugging Face offline mode and disabled telemetry.
It loads the weights before opening the listener. Requests cannot select another
model, a repository, an adapter or a path.

The only model name accepted by the HTTP contract is `myshka-family`. The server
uses non-thinking generation, at most 180 generated tokens, a 1,024-token KV
cache, a 12 GiB MLX allocation limit and a 128 MiB MLX cache limit. These are
runtime limits, not a guarantee about total process or system memory usage.

## Authentication and transport

Supply a random bearer value of 32–256 URL-safe characters in a private regular
file owned by the service user. The file must have no group or other access
(normally mode `0600`) and must not be a symlink. Keep it out of Git. The CLI
accepts the **file path**, never a token argument.

The default listener is `127.0.0.1:11535`. A typical explicit invocation is:

```sh
python scripts/local_family_server.py \
  --model-path /absolute/private/path/to/verified-model \
  --bearer-file /absolute/private/path/to/bearer.txt \
  --bind 127.0.0.1 --port 11535
```

For a remote HA host, prefer an authenticated SSH tunnel between loopback
listeners. Do not expose this plain HTTP endpoint to the Internet. An explicit
private interface address is supported, but unspecified addresses such as
`0.0.0.0` and `::` are rejected. This guide does not open ports, configure a
tunnel or install a background service.

HA uses the local route with its usual private configuration:

```yaml
myshka_family:
  ollama_url: http://127.0.0.1:11535
  ollama_api_key: !secret myshka_local_creative_key
  model: myshka-family
```

The loopback address above must refer to a tunnel endpoint reachable **from the
HA process**. The key is sent only as an Authorization header on the local HTTP
route; it is not inserted into the prompt or any optional public creative route.
HTTP redirects are disabled. Do not configure `public_creative_uri` when choosing
the local route.

## Request and failure boundaries

Only `POST /api/chat` is supported. A valid bearer is required before the body is
read. Bodies are limited to 8 KiB; duplicate JSON fields, chunked/compressed
requests, model changes, history, tools, images and nonstandard options are
rejected. The two messages must contain the exact shared system prompt and a
JSON creative request with only `вид` and `тема`. The kind is a poem, story or
nursery rhyme; the topic is bounded to 180 characters. The shared prompt asks
for four-line verse or a complete story of at most 60 words to fit the token
budget; this is a generation instruction, not a guaranteed word-count validator. The server reconstructs
the messages from that contract.

One generation runs at a time. Another request receives `503 busy` instead of
joining a queue. Generation has a 20-second budget checked between yielded
tokens. A native GPU operation cannot be forcibly interrupted by this Python
check: a slow operation is rejected when it returns, and HA independently stops
waiting at its 25-second deadline. A stuck native operation requires service
recovery; the server does not start overlapping inference to hide it.

Truncation retains `done_reason: length`, so HA refuses to speak an unfinished
answer. Failure responses contain generic codes. Request bodies, bearer values,
prompts and generated replies are not logged. The process retains loaded model
weights but no conversation history.

Protocol tests use a fake generator and in-memory HTTP requests:

```sh
python -m unittest discover -s tests -p test_local_family_server.py -v
```

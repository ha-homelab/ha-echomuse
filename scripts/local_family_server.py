#!/usr/bin/env python3
"""Authenticated fixed-model MLX creative endpoint; no model management API.

Importing this module neither loads MLX nor opens a listener. The CLI loads an
existing absolute model directory offline, then serves one bounded generation
at a time. It never logs request bodies, bearer values, prompts or replies.
"""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import threading
import time

_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "custom_components/myshka_family/creative_contract.py"
_SPEC = importlib.util.spec_from_file_location("local_family_contract", _CONTRACT_PATH)
contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(contract)

MAX_BODY_BYTES = 8192
MAX_TEXT_CHARS = 1200
MAX_TOKENS = 180
MAX_KV_SIZE = 1024
GENERATION_SECONDS = 20
SOCKET_SECONDS = 5
MAX_CONNECTIONS = 8
MEMORY_BYTES = 12 * 1024**3
CACHE_BYTES = 128 * 1024**2


class ServiceError(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status, self.code = status, code


def validate_bind(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("Bind must be a literal local IP address") from exc
    if not address.is_private or address.is_unspecified or address.is_multicast:
        raise ValueError("Bind must name a specific private or loopback interface")
    return str(address)


def validate_model_path(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Model path must be absolute")
    path = path.resolve(strict=True)
    if not path.is_dir() or not (path / "config.json").is_file() or not any(path.glob("*.safetensors")):
        raise ValueError("Model directory must already contain config and safetensors weights")
    return path


def load_bearer(path):
    """Read a current-user-owned, non-symlink file with no group/other access."""
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("Bearer file path must be absolute")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("Bearer file must be a private regular file owned by this user")
        if not 32 <= info.st_size <= 258:
            raise ValueError("Invalid bearer file length")
        data = os.read(descriptor, 258)
    finally:
        os.close(descriptor)
    try:
        value = data.decode("ascii").rstrip("\r\n")
    except UnicodeError as exc:
        raise ValueError("Invalid bearer file") from exc
    return contract.validate_api_key(value)


def configure_offline_environment():
    # Set, rather than default, these flags before importing either runtime.
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "HF_HUB_DISABLE_IMPLICIT_TOKEN"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


class MLXGenerator:
    def __init__(self, model_path):
        configure_offline_environment()
        # Lazy imports keep protocol/security tests free of MLX or model loads.
        import mlx.core as mx
        from mlx_lm import load, stream_generate
        from mlx_lm.sample_utils import make_sampler

        mx.set_memory_limit(MEMORY_BYTES)
        mx.set_cache_limit(CACHE_BYTES)
        self.mx = mx
        self.stream_generate = stream_generate
        self.sampler = make_sampler(temp=0.7, top_p=0.8, top_k=20, min_p=0.0)
        self.model, self.tokenizer = load(
            str(model_path), trust_remote_code=False,
            tokenizer_config={"trust_remote_code": False, "local_files_only": True},
        )
        mx.eval(self.model.parameters())
        mx.synchronize()

    def __call__(self, messages):
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, enable_thinking=False,
        )
        if len(prompt) > MAX_KV_SIZE - MAX_TOKENS:
            raise ServiceError(422, "prompt_too_long")
        yield from self.stream_generate(
            self.model, self.tokenizer, prompt, max_tokens=MAX_TOKENS,
            sampler=self.sampler, max_kv_size=MAX_KV_SIZE, prefill_step_size=256,
        )


class InferenceEngine:
    def __init__(self, bearer, generator, *, clock=time.monotonic):
        self.bearer = bearer
        self.generator = generator
        self.clock = clock
        self.lock = threading.Lock()

    def infer(self, messages):
        if not self.lock.acquire(blocking=False):
            raise ServiceError(503, "busy")
        iterator = None
        try:
            started = self.clock()
            iterator = iter(self.generator(messages))
            chunks, size, count, finish_reason = [], 0, 0, None
            while True:
                if self.clock() - started >= GENERATION_SECONDS:
                    raise ServiceError(504, "generation_timeout")
                try:
                    chunk = next(iterator)
                except StopIteration:
                    break
                # A native GPU operation cannot be preempted inside next();
                # enforce the deadline as soon as control returns to Python.
                if self.clock() - started >= GENERATION_SECONDS:
                    raise ServiceError(504, "generation_timeout")
                count += 1
                text = getattr(chunk, "text", None)
                if not isinstance(text, str) or count > MAX_TOKENS + 1:
                    raise ServiceError(502, "invalid_generation")
                size += len(text)
                if size > MAX_TEXT_CHARS:
                    raise ServiceError(502, "reply_too_long")
                chunks.append(text)
                finish_reason = getattr(chunk, "finish_reason", None)
            # Exhaustion can include native GPU synchronization after the
            # final yield. It is part of the request's generation budget.
            if self.clock() - started >= GENERATION_SECONDS:
                raise ServiceError(504, "generation_timeout")
            content = "".join(chunks).strip()
            if (not content or finish_reason not in {"stop", "length"}
                    or "<" in content or ">" in content or not re.search("[А-Яа-я]", content)):
                raise ServiceError(502, "invalid_generation")
            return {"model": contract.MODEL_ALIAS, "message": {"role": "assistant", "content": content},
                    "done": True, "done_reason": finish_reason}
        finally:
            try:
                if iterator is not None and hasattr(iterator, "close"):
                    iterator.close()
            finally:
                self.lock.release()


class FamilyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "MyshkaFamily"
    sys_version = ""

    def setup(self):
        self.request.settimeout(SOCKET_SECONDS)
        super().setup()

    def log_message(self, *_):
        # BaseHTTPRequestHandler otherwise logs request paths and errors.
        pass

    def send_error(self, code, message=None, explain=None):
        self.reply(code, {"error": "invalid_http_request"})

    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        self.reply(405, {"error": "post_required"})

    do_HEAD = do_GET
    do_OPTIONS = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET

    def do_POST(self):
        if self.path != "/api/chat":
            self.reply(404, {"error": "not_found"})
            return
        values = self.headers.get_all("Authorization", [])
        expected = "Bearer " + self.server.engine.bearer
        if len(values) != 1 or not hmac.compare_digest(values[0].encode("utf-8"), expected.encode("utf-8")):
            self.reply(401, {"error": "unauthorized"})
            return
        if self.server.engine.lock.locked():
            self.reply(503, {"error": "busy"})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if (len(lengths) != 1 or not re.fullmatch(r"[0-9]+", lengths[0])
                or "Transfer-Encoding" in self.headers or "Content-Encoding" in self.headers):
            self.reply(400, {"error": "invalid_framing"})
            return
        if len(lengths[0]) > 5:
            self.reply(413, {"error": "body_too_large"})
            return
        length = int(lengths[0])
        if not 0 < length <= MAX_BODY_BYTES:
            self.reply(413, {"error": "body_too_large"})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "json_required"})
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Truncated request")
            payload = json.loads(raw.decode("utf-8"), object_pairs_hook=contract.reject_duplicate_keys)
            messages = contract.validate_payload(payload)
        except TimeoutError:
            self.reply(408, {"error": "request_timeout"})
            return
        except (ValueError, TypeError, UnicodeError, RecursionError):
            self.reply(400, {"error": "invalid_request"})
            return
        try:
            self.reply(200, self.server.engine.infer(messages))
        except ServiceError as exc:
            self.reply(exc.status, {"error": exc.code})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            self.reply(503, {"error": "generation_failed"})


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 4

    def __init__(self, address, engine):
        self.engine = engine
        self.connections = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self.address_family = socket.AF_INET6 if ipaddress.ip_address(address[0]).version == 6 else socket.AF_INET
        super().__init__(address, FamilyHandler)

    def process_request(self, request, client_address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()

    def handle_error(self, request, client_address):
        # No request details, token values or exception tracebacks in logs.
        print("Family server: request failed.", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True, help="Absolute path to pre-downloaded, reviewed weights")
    parser.add_argument("--bearer-file", required=True, help="Absolute path to a private random bearer file")
    parser.add_argument("--bind", default="127.0.0.1", help="Specific private/loopback IP, never an unspecified address")
    parser.add_argument("--port", type=int, default=11535)
    args = parser.parse_args(argv)
    try:
        bind = validate_bind(args.bind)
        if not 1 <= args.port <= 65535:
            raise ValueError("Port is out of range")
        model_path = validate_model_path(args.model_path)
        bearer = load_bearer(args.bearer_file)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2
    generator = MLXGenerator(model_path)
    server = BoundedHTTPServer((bind, args.port), InferenceEngine(bearer, generator))
    print("Family creative server ready: fixed model, offline weights.", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        # Ctrl-C requests a clean shutdown; server_close runs below.
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

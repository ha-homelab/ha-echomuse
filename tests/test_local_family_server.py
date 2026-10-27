"""Exercise the fixed-model HTTP protocol without MLX, sockets or listeners."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "scripts/local_family_server.py"
SPEC = importlib.util.spec_from_file_location("local_family_server", PATH)
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)
DUMMY_BEARER = "test-" + "x" * 48


class FakeSocket:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = io.BytesIO()
        self.timeout = None

    def makefile(self, mode, *args):
        assert mode == "rb"
        return self.input

    def sendall(self, data):
        self.output.write(data)

    def settimeout(self, value):
        self.timeout = value


class MainLifecycleTest(unittest.TestCase):
    def test_normal_and_interrupted_shutdown_close_server_and_exit_successfully(self):
        for interruption in (None, KeyboardInterrupt):
            with self.subTest(interruption=interruption), \
                    patch.object(server, "validate_bind", return_value="127.0.0.1"), \
                    patch.object(server, "validate_model_path", return_value=Path("/model")), \
                    patch.object(server, "load_bearer", return_value=DUMMY_BEARER), \
                    patch.object(server, "MLXGenerator"), \
                    patch.object(server, "BoundedHTTPServer") as constructor, \
                    redirect_stdout(io.StringIO()):
                instance = constructor.return_value
                instance.serve_forever.side_effect = interruption
                result = server.main(["--model-path", "/model", "--bearer-file", "/bearer"])
                instance.server_close.assert_called_once_with()
                self.assertEqual(result, 0)


def payload():
    return {"model": server.contract.MODEL_ALIAS, "stream": False, "think": False, "keep_alive": -1,
            "messages": server.contract.creative_messages("стих", "зайке"),
            "options": dict(server.contract.CREATIVE_OPTIONS)}


class LocalFamilyServerTest(unittest.TestCase):
    def setUp(self):
        self.received = []

        def generate(messages):
            self.received.append(messages)
            yield SimpleNamespace(text="Зайка слушает ручей.\nСтал весенний день теплей.", finish_reason="stop")

        self.engine = server.InferenceEngine(DUMMY_BEARER, generate)

    def request(self, data=None, *, method="POST", target="/api/chat", headers=None, raw=None):
        if raw is None:
            raw = json.dumps(payload() if data is None else data, ensure_ascii=False).encode()
        pairs = [("Host", "localhost"), ("Authorization", "Bearer " + DUMMY_BEARER),
                 ("Content-Type", "application/json"), ("Content-Length", str(len(raw)))]
        if headers is not None:
            pairs = headers
        wire = (method + " " + target + " HTTP/1.1\r\n" + "\r\n".join(f"{key}: {value}" for key, value in pairs)
                + "\r\n\r\n").encode() + raw
        sock = FakeSocket(wire)
        captured = io.StringIO()
        with redirect_stdout(captured), redirect_stderr(captured):
            server.FamilyHandler(sock, ("127.0.0.1", 12345), SimpleNamespace(engine=self.engine))
        self.assertEqual(captured.getvalue(), "")
        self.assertEqual(sock.timeout, server.SOCKET_SECONDS)
        head, body = sock.output.getvalue().split(b"\r\n\r\n", 1)
        status = int(head.split(b" ")[1])
        return status, json.loads(body) if body else None, head.decode()

    def test_authenticated_bounded_request_returns_ollama_compatible_reply(self):
        status, body, headers = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(body["model"], "myshka-family")
        self.assertTrue(body["done"])
        self.assertEqual(body["done_reason"], "stop")
        self.assertIn("Зайка", body["message"]["content"])
        self.assertEqual(self.received, [server.contract.creative_messages("стих", "зайке")])
        self.assertIn("Cache-Control: no-store", headers)
        self.assertIn("Connection: close", headers)

    def test_missing_wrong_or_duplicate_bearer_never_generates(self):
        for auth in ([], [("Authorization", "Bearer wrong")],
                     [("Authorization", "Bearer " + DUMMY_BEARER)] * 2):
            with self.subTest(auth_count=len(auth)):
                status, body, _ = self.request(headers=auth)
                self.assertEqual(status, 401)
                self.assertEqual(body, {"error": "unauthorized"})
        self.assertEqual(self.received, [])

    def test_only_exact_chat_post_is_supported(self):
        for method, path, expected in (("GET", "/api/chat", 405), ("POST", "/api/pull", 404),
                                       ("POST", "/api/chat?model=other", 404), ("PUT", "/api/chat", 405),
                                       ("POST", "/v1/chat/completions", 404)):
            with self.subTest(method=method, path=path):
                self.assertEqual(self.request(method=method, target=path)[0], expected)
        self.assertEqual(self.received, [])

    def test_framing_size_compression_and_media_type_are_validated(self):
        base = [("Authorization", "Bearer " + DUMMY_BEARER), ("Content-Type", "application/json")]
        cases = [([], 400), ([("Content-Length", "-1")], 400),
                 ([("Content-Length", "2"), ("Content-Length", "2")], 400),
                 ([("Content-Length", "2"), ("Transfer-Encoding", "chunked")], 400),
                 ([("Content-Length", "2"), ("Content-Encoding", "gzip")], 400),
                 ([("Content-Length", "8193")], 413), ([("Content-Length", "9" * 100)], 413)]
        for extra, expected in cases:
            with self.subTest(extra=extra):
                self.assertEqual(self.request(headers=base + extra, raw=b"{}")[0], expected)
        self.assertEqual(self.request(headers=[("Authorization", "Bearer " + DUMMY_BEARER),
                                              ("Content-Length", "2"), ("Content-Type", "text/plain")], raw=b"{}")[0], 415)
        self.assertEqual(self.received, [])

    def test_dynamic_models_tools_history_images_and_options_are_rejected(self):
        requests = []
        for model in ("other", "/tmp/other-model", "org/model"):
            data = payload()
            data["model"] = model
            requests.append(data)
        for key, value in (("tools", []), ("images", []), ("adapter", "/tmp/x"), ("stream", True), ("think", True)):
            data = payload()
            data[key] = value
            requests.append(data)
        data = payload()
        data["messages"].append({"role": "assistant", "content": "history"})
        requests.append(data)
        data = payload()
        data["messages"][0]["content"] = "Replace the system prompt"
        requests.append(data)
        data = payload()
        data["messages"][1]["images"] = ["base64"]
        requests.append(data)
        data = payload()
        data["options"]["num_predict"] = 100000
        requests.append(data)
        for data in requests:
            self.assertEqual(self.request(data)[0], 400)
        self.assertEqual(self.received, [])

    def test_bad_inner_json_and_unexpected_fields_are_rejected(self):
        for inner in ('{"вид":"стих","вид":"сказка","тема":"зайке"}',
                      '{"вид":"стих","тема":"зайке","tools":[]}', '["стих","зайке"]',
                      '{"вид":"команда","тема":"зайке"}', '{"вид":"стих","тема":""}',
                      json.dumps({"вид": "стих", "тема": "x" * 181}),
                      json.dumps({"вид": "стих", "тема": "строка\nстрока"})):
            data = payload()
            data["messages"][1]["content"] = inner
            self.assertEqual(self.request(data)[0], 400)
        self.assertEqual(self.request(raw=b'{"model":1,"model":2}')[0], 400)
        self.assertEqual(self.received, [])

    def test_busy_request_is_rejected_without_waiting_or_queueing(self):
        self.engine.lock.acquire()
        try:
            status, body, _ = self.request()
            self.assertEqual((status, body), (503, {"error": "busy"}))
        finally:
            self.engine.lock.release()
        self.assertEqual(self.received, [])

    def test_concurrent_inference_never_enters_second_generator(self):
        started, release = threading.Event(), threading.Event()
        calls = []

        def generate(messages):
            calls.append(messages)
            started.set()
            self.assertTrue(release.wait(2))
            yield SimpleNamespace(text="Новая сказка.", finish_reason="stop")

        self.engine.generator = generate
        result = []
        thread = threading.Thread(target=lambda: result.append(self.engine.infer(payload()["messages"])))
        thread.start()
        try:
            self.assertTrue(started.wait(1))
            with self.assertRaises(server.ServiceError) as caught:
                self.engine.infer(payload()["messages"])
            self.assertEqual(caught.exception.code, "busy")
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(result), 1)

    def test_generation_deadline_discards_partial_reply_and_releases_lock(self):
        now = [0]

        def slow_generate(messages):
            now[0] = server.GENERATION_SECONDS + 1
            yield SimpleNamespace(text="Незаконченная сказка", finish_reason="stop")

        self.engine = server.InferenceEngine(DUMMY_BEARER, slow_generate, clock=lambda: now[0])
        status, body, _ = self.request()
        self.assertEqual(status, 504)
        self.assertEqual(body, {"error": "generation_timeout"})
        self.assertFalse(self.engine.lock.locked())

    def test_slow_final_cleanup_cannot_return_success_after_deadline(self):
        now = [0.0]

        def slow_cleanup(messages):
            yield SimpleNamespace(text="Готовая сказка.", finish_reason="stop")
            now[0] = server.GENERATION_SECONDS + 1

        self.engine = server.InferenceEngine(DUMMY_BEARER, slow_cleanup, clock=lambda: now[0])
        status, body, _ = self.request()
        self.assertEqual((status, body), (504, {"error": "generation_timeout"}))
        self.assertFalse(self.engine.lock.locked())

    def test_length_stop_preserves_truncation_signal(self):
        self.engine.generator = lambda messages: iter([SimpleNamespace(text="Незаконченный текст", finish_reason="length")])
        status, body, _ = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(body["done_reason"], "length")

    def test_generation_failure_is_generic_and_never_echoes_secrets(self):
        def fail(messages):
            raise RuntimeError(DUMMY_BEARER + " private transcript")

        self.engine.generator = fail
        status, body, _ = self.request()
        self.assertEqual((status, body), (503, {"error": "generation_failed"}))
        self.assertFalse(self.engine.lock.locked())

    def test_bad_or_oversized_output_is_not_sent_as_answer(self):
        for text in ("я" * 1201, "<think>Секрет</think>", "", "Only English"):
            self.engine.generator = lambda messages: iter([SimpleNamespace(text=text, finish_reason="stop")])
            status, body, _ = self.request()
            self.assertEqual(status, 502)
            self.assertNotIn("message", body)
            self.assertFalse(self.engine.lock.locked())

    def test_private_bearer_file_permissions_and_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bearer.txt"
            path.write_text(DUMMY_BEARER + "\n")
            path.chmod(0o600)
            self.assertEqual(server.load_bearer(path), DUMMY_BEARER)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                server.load_bearer(path)
            path.chmod(0o600)
            path.write_text("x" * 300)
            with self.assertRaises(ValueError):
                server.load_bearer(path)
            path.write_text("short")
            with self.assertRaises(ValueError):
                server.load_bearer(path)

    def test_bearer_validation_rejects_header_injection_and_short_values(self):
        for value in ("short", "x" * 257, "x" * 40 + "\r\nX-Test: value", None, "x" * 40 + " "):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                server.contract.validate_api_key(value)

    def test_bind_and_model_path_do_not_allow_public_listener_or_remote_model(self):
        self.assertEqual(server.validate_bind("127.0.0.1"), "127.0.0.1")
        self.assertEqual(server.validate_bind("::1"), "::1")
        for host in ("0.0.0.0", "::", ".".join(["8"] * 4), "example.com", ".".join(("224", "0", "0", "1"))):
            with self.subTest(host=host), self.assertRaises(ValueError):
                server.validate_bind(host)
        with self.assertRaises(ValueError):
            server.validate_model_path("org/model")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            with self.assertRaises(ValueError):
                server.validate_model_path(path)
            (path / "config.json").write_text("{}")
            (path / "model.safetensors").write_bytes(b"fixture")
            self.assertEqual(server.validate_model_path(path), path.resolve())


if __name__ == "__main__":
    unittest.main()

"""Offline protocol tests: no network, HA instance, microphone or playback."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "custom_components/echomuse_home/announcement_protocol.py"
SPEC = importlib.util.spec_from_file_location("announcement_protocol", PATH)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
RID = "announce-" + "a" * 32 + "-223"


def caps(**changes):
    return {"protocol": p.PROTOCOL, "boot_id": "boot-1", **dict.fromkeys(p.CAPABILITIES, True), **changes}


def result(status="accepted", **changes):
    return {"protocol": p.PROTOCOL, "boot_id": "boot-1", "request_id": RID, "status": status, **changes}


class ProtocolTest(unittest.TestCase):
    def test_capability_claims_are_fail_closed(self):
        for invalid in ({}, None, caps(protocol="other"), caps(boot_id=""), caps(dedup=1), caps(owned_cancel="false")):
            with self.subTest(invalid=invalid):
                self.assertFalse(all(p.capabilities(invalid)[k] for k in p.CAPABILITIES))
        self.assertTrue(all(p.capabilities(caps())[k] for k in p.CAPABILITIES))
        self.assertTrue(all(p.capabilities(caps(**dict.fromkeys(p.CAPABILITIES, "true")))[k] for k in p.CAPABILITIES))

    def test_duck_capability_is_explicit_and_requires_base_contract(self):
        for data in (caps(), caps(duck_music=False), caps(duck_music=1), caps(duck_music="yes"), caps(duck_music=True, owned_cancel=False)):
            self.assertIs(p.capabilities(data)["duck_music"], False)
        for value in (True, "true"):
            self.assertIs(p.capabilities(caps(duck_music=value))["duck_music"], True)

    def test_receipts_require_protocol_request_and_boot(self):
        for changes in ({"request_id": "other"}, {"protocol": "other"}, {"boot_id": ""}, {"boot_id": "boot-2"}, {"status": "ok"}):
            with self.subTest(changes=changes):
                self.assertEqual(p.receipt(result(**changes), RID, boot_id="boot-1")["status"], "unknown")
        self.assertEqual(p.receipt(result("completed"), RID, boot_id="boot-1")["status"], "completed")

    def test_sensitive_unstructured_reason_is_removed(self):
        receipt = p.receipt(result("failed", reason="http://secret/path?token=x", media_id="secret"), RID)
        self.assertNotIn("reason", receipt)
        self.assertNotIn("media_id", receipt)

    def test_request_and_media_boundaries(self):
        p.request_id(RID)
        for invalid in (None, "", RID + "\n", RID.upper(), "announce-" + "a" * 31 + "-223"):
            with self.assertRaises(ValueError): p.request_id(invalid)
        for valid in ("http://ha.local/test.wav", "https://ha.local/api/tts_proxy/test.wav?authSig=test", "/local/test.wav", "media-source://media_source/local/test.wav"):
            self.assertEqual(p.media_id(valid), valid)
        for invalid in ("media-source://tts/provider?message=hello", "file:///etc/passwd", "http://u:p@ha/test", "//other/path", "https://ha/x#y", "https://ha/\nx"):
            with self.assertRaises(ValueError): p.media_id(invalid)


class BrokerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls, self.saved = [], []
        self.clock = 1000
        self.reply = result()
        self.capabilities = caps()
        self.raise_submit = False

        async def send(target, operation, args):
            self.calls.append((target, operation, args))
            if operation == "capabilities": return self.capabilities
            if operation in {"submit", "submit_duck"} and self.raise_submit: raise TimeoutError()
            if operation == "status": return result("playing")
            if operation == "stop": return result("stopped")
            return self.reply

        async def resolve(source):
            return "http://ha.local/api/tts_proxy/rendered.wav?authSig=private"

        async def save(records):
            self.saved.append(dict(records))

        self.send, self.resolve, self.save = send, resolve, save
        self.broker = p.AnnouncementBroker(send, resolve, save, now=lambda: self.clock)

    async def submit(self, **changes):
        return await self.broker.submit("target", identity="device-1", rid=RID,
                                        **{"source": "/local/rendered.wav", "expires_at": 1100, **changes})

    def submitted(self):
        return [row for row in self.calls if row[1] in {"submit", "submit_duck"}]

    async def test_only_native_receipt_can_complete(self):
        response = await self.submit()
        self.assertEqual(response["status"], "accepted")
        self.assertEqual(len(self.submitted()), 1)
        self.assertEqual(self.submitted()[0][2]["expires_at"], "1100")
        self.assertEqual(len(self.saved), 1)
        self.assertNotIn("authSig", str(self.saved))
        self.assertNotIn("rendered.wav", str(self.saved))

    async def test_timeout_is_unknown_and_retry_only_reads(self):
        self.raise_submit = True
        self.assertEqual((await self.submit())["status"], "unknown")
        self.assertEqual((await self.submit())["status"], "playing")
        self.assertEqual(len(self.submitted()), 1)

    async def test_reloaded_ledger_never_dispatches_again(self):
        await self.submit()
        self.broker = p.AnnouncementBroker(self.send, self.resolve, self.save, now=lambda: self.clock, records=self.saved[-1])
        await self.submit()
        self.assertEqual(len(self.submitted()), 1)

    async def test_conflicting_reuse_is_rejected(self):
        await self.submit()
        self.assertEqual((await self.submit(source="/local/other.wav"))["reason"], "request_id_conflict")
        self.assertEqual(len(self.submitted()), 1)

    async def test_concurrent_retries_dispatch_once(self):
        await asyncio.gather(*[self.submit() for _ in range(10)])
        self.assertEqual(len(self.submitted()), 1)

    async def test_stock_or_partial_capabilities_never_dispatch(self):
        self.capabilities = caps(honest_completion=False)
        self.assertEqual((await self.submit())["status"], "skipped")
        self.assertEqual(self.submitted(), [])
        self.assertEqual(self.saved, [])

    async def test_unsupported_duck_never_falls_back_to_skip(self):
        self.assertEqual((await self.submit(policy="duck_music"))["reason"], "duck_music_unavailable")
        self.assertEqual(self.submitted(), [])
        self.assertEqual(self.saved, [])

    async def test_duck_dispatches_only_dedicated_action(self):
        self.capabilities = caps(duck_music=True)
        self.assertEqual((await self.submit(policy="duck_music"))["status"], "accepted")
        self.assertEqual([row[1] for row in self.submitted()], ["submit_duck"])
        self.assertEqual(set(self.submitted()[0][2]), {"request_id", "media_id", "expires_at"})

    async def test_skip_to_duck_same_id_is_conflict(self):
        await self.submit()
        self.capabilities = caps(duck_music=True)
        self.assertEqual((await self.submit(policy="duck_music"))["reason"], "request_id_conflict")
        self.assertEqual([row[1] for row in self.submitted()], ["submit"])

    async def test_duck_to_skip_same_id_is_conflict(self):
        self.capabilities = caps(duck_music=True)
        await self.submit(policy="duck_music")
        self.assertEqual((await self.submit())["reason"], "request_id_conflict")
        self.assertEqual([row[1] for row in self.submitted()], ["submit_duck"])

    async def test_legacy_skip_fingerprint_is_preserved(self):
        old = hashlib.sha256(json.dumps(["/local/rendered.wav", 1100], separators=(",", ":")).encode()).hexdigest()
        self.broker = p.AnnouncementBroker(self.send, self.resolve, self.save, now=lambda: self.clock,
            records={"device-1:" + RID: {"fingerprint": old, "expires_at": 1100}})
        self.assertEqual((await self.submit())["status"], "playing")
        self.assertEqual(self.submitted(), [])

    async def test_uncertain_duck_retry_only_queries_status(self):
        self.capabilities = caps(duck_music=True)
        self.raise_submit = True
        self.assertEqual((await self.submit(policy="duck_music"))["status"], "unknown")
        self.assertEqual((await self.submit(policy="duck_music"))["status"], "playing")
        self.assertEqual(len(self.submitted()), 1)

    async def test_invalid_policy_is_rejected_before_native_io(self):
        for policy in ("interrupt", "duck", None, True):
            with self.assertRaises(ValueError): await self.submit(policy=policy)
        self.assertEqual(self.calls, [])

    async def test_deadline_and_boolean_validation(self):
        for expiration in (999, 1000, 1181):
            self.assertEqual((await self.submit(expires_at=expiration))["status"], "skipped")
        for expiration in (True, 1100.0, "1100"):
            with self.assertRaises(ValueError): await self.submit(expires_at=expiration)
        self.assertEqual(self.submitted(), [])

    async def test_expiration_during_resolution_prevents_dispatch(self):
        async def slow(source):
            self.clock = 1101
            return "http://ha.local/test.wav"
        self.broker.resolve = slow
        self.assertEqual((await self.submit())["reason"], "expired_before_dispatch")
        self.assertEqual(self.submitted(), [])

    async def test_persistence_failure_prevents_dispatch(self):
        async def disk_full(records): raise OSError("private-path")
        self.broker.save = disk_full
        self.assertEqual((await self.submit())["reason"], "ledger_persistence_failed")
        self.assertEqual(self.submitted(), [])

    async def test_restart_between_capability_and_submit_is_unknown(self):
        self.reply = result(boot_id="boot-2", status="completed")
        self.assertEqual((await self.submit())["status"], "unknown")

    async def test_status_and_owned_stop_never_submit(self):
        self.assertEqual((await self.broker.get_status("target", RID))["status"], "playing")
        self.assertEqual((await self.broker.stop("target", RID))["status"], "stopped")
        self.assertEqual(self.submitted(), [])
        self.assertEqual(self.calls[-1][2], {"request_id": RID})

    async def test_status_and_stop_survive_unavailable_admission_ledger(self):
        self.broker.ready = lambda: False
        self.assertFalse((await self.broker.get_capabilities("target"))["dedup"])
        self.assertEqual((await self.broker.get_status("target", RID))["status"], "playing")
        self.assertEqual((await self.broker.stop("target", RID))["status"], "stopped")
        self.assertEqual([row[1] for row in self.calls], ["status", "stop"])

    async def test_owned_stop_does_not_depend_on_capability_probe(self):
        async def send(target, operation, data):
            if operation == "capabilities": raise TimeoutError()
            self.assertEqual(operation, "stop")
            return result("stopped")
        self.broker.send = send
        self.assertEqual((await self.broker.stop("target", RID))["status"], "stopped")

    async def test_owned_stop_rejects_another_request_receipt(self):
        async def send(target, operation, data): return result("stopped", request_id="other")
        self.broker.send = send
        self.assertEqual((await self.broker.stop("target", RID))["status"], "unknown")

    async def test_malformed_ledger_is_not_silently_discarded(self):
        with self.assertRaises(ValueError):
            p.AnnouncementBroker(self.send, self.resolve, self.save, records={"key": {"fingerprint": "bad", "expires_at": 1000}})


if __name__ == "__main__":
    unittest.main()

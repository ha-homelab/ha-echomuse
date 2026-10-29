"""Quiet, fail-closed orchestration for device-owned announcement requests.

This module does not synthesize speech, call Assist or infer success from a
transport acknowledgement. Only the guarded native endpoint owns playback.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import hashlib
import json
import re
import time
from typing import Any
from urllib.parse import urlsplit

PROTOCOL = "cisco-announcement-v1"
CAPABILITIES = (
    "atomic_idle_guard", "dedup", "owned_cancel", "honest_completion",
    "deadline_enforced",
)
STATUSES = frozenset({"accepted", "playing", "completed", "skipped", "failed", "stopped", "unknown"})
REQUEST_ID = re.compile(r"announce-[0-9a-f]{32}-[0-9]{3}\Z")
MAX_DEADLINE = 180
MAX_RECORDS = 1024
RETENTION = 7 * 86400


def request_id(value: Any) -> str:
    if not isinstance(value, str) or REQUEST_ID.fullmatch(value) is None:
        raise ValueError("Invalid announcement request_id")
    return value


def media_id(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("A bounded, pre-rendered media_id is required")
    if any(ord(c) < 32 for c in value):
        raise ValueError("Invalid media_id")
    parts = urlsplit(value)
    if parts.username or parts.password or parts.fragment:
        raise ValueError("Credentials and fragments are not allowed in media_id")
    # A TTS media source is a synthesis request, not the already rendered file.
    if parts.scheme == "media-source":
        if parts.netloc != "media_source":
            raise ValueError("Only pre-rendered local media sources are supported")
    elif parts.scheme in {"http", "https"}:
        if not parts.hostname:
            raise ValueError("Invalid media URL")
    elif parts.scheme or not value.startswith("/") or value.startswith("//"):
        raise ValueError("Use an HTTP URL, HA path or local media source")
    return value


def failed(rid: str, reason: str, *, status: str = "unknown") -> dict[str, Any]:
    return {"request_id": rid, "status": status, "reason": reason}


def capabilities(payload: Any) -> dict[str, Any]:
    """Never turn missing/malformed native claims into affirmative support."""
    data = payload if isinstance(payload, dict) else {}
    valid = data.get("protocol") == PROTOCOL and isinstance(data.get("boot_id"), str) and bool(data["boot_id"])
    result = {"protocol": PROTOCOL, **{key: valid and (data.get(key) is True or data.get(key) == "true") for key in CAPABILITIES}}
    result["duck_music"] = all(result[key] for key in CAPABILITIES) and (data.get("duck_music") is True or data.get("duck_music") == "true")
    if valid:
        result["boot_id"] = data["boot_id"][:128]
    if not all(result[key] for key in CAPABILITIES):
        result["reason"] = "guarded_endpoint_unavailable"
    return result


def receipt(payload: Any, rid: str, *, boot_id: str | None = None) -> dict[str, Any]:
    """A reply is evidence only for the exact request, protocol and current boot."""
    if not isinstance(payload, dict) or payload.get("request_id") != rid or payload.get("protocol") != PROTOCOL:
        return failed(rid, "invalid_native_receipt")
    if not isinstance(payload.get("boot_id"), str) or not payload["boot_id"]:
        return failed(rid, "missing_native_boot_id")
    if boot_id is not None and payload["boot_id"] != boot_id:
        return failed(rid, "device_restarted")
    status = payload.get("status")
    if status not in STATUSES:
        return failed(rid, "invalid_native_status")
    result = {"request_id": rid, "status": status, "boot_id": payload["boot_id"][:128]}
    reason = payload.get("reason")
    # Reasons are machine tokens, never URLs, transcripts or native exceptions.
    if isinstance(reason, str) and re.fullmatch(r"[a-z0-9_:-]{1,100}", reason):
        result["reason"] = reason
    return result


class AnnouncementBroker:
    """Persist dispatch intent before sending; retries only ask native status.

    The ledger contains request fingerprints and deadlines, never audio URLs or
    text. It is not a playback-state cache. Native receipts remain authoritative.
    """
    def __init__(self, send: Callable[..., Awaitable[dict]], resolve: Callable[..., Awaitable[str]],
                 save: Callable[[dict], Awaitable[None]], *, now: Callable[[], float] = time.time,
                 records: dict | None = None, ready: Callable[[], bool] = lambda: True):
        self.send, self.resolve, self.save, self.now = send, resolve, save, now
        self.ready = ready
        self.records: dict[str, dict] = {}
        self.lock = asyncio.Lock()
        if len(records or {}) > MAX_RECORDS:
            raise ValueError("Oversized dispatch ledger")
        for key, row in (records or {}).items():
            if (isinstance(key, str) and isinstance(row, dict)
                and isinstance(row.get("fingerprint"), str) and re.fullmatch(r"[a-f0-9]{64}", row["fingerprint"])
                and type(row.get("expires_at")) is int):
                self.records[key] = {"fingerprint": row["fingerprint"], "expires_at": row["expires_at"]}
            else:
                raise ValueError("Invalid dispatch ledger")

    async def get_capabilities(self, target: Any) -> dict:
        if not self.ready():
            return {**capabilities(None), "reason": "ledger_unavailable"}
        try:
            return capabilities(await self.send(target, "capabilities", {}))
        except Exception:
            return capabilities(None)

    async def get_status(self, target: Any, rid: str) -> dict:
        request_id(rid)
        try:
            return receipt(await self.send(target, "status", {"request_id": rid}), rid)
        except Exception:
            return failed(rid, "native_status_unavailable")

    async def stop(self, target: Any, rid: str) -> dict:
        request_id(rid)
        try:
            # Cancellation is not new admission. A damaged local ledger or a
            # failed capabilities probe must not prevent stopping an owned ID.
            # The bound native action still validates exact request ownership.
            return receipt(await self.send(target, "stop", {"request_id": rid}), rid)
        except Exception:
            return failed(rid, "native_stop_unconfirmed")

    async def submit(self, target: Any, *, identity: str, rid: str, source: str, expires_at: int, policy: str = "skip") -> dict:
        request_id(rid)
        media_id(source)
        if type(expires_at) is not int:
            raise ValueError("expires_at must be integer Unix UTC seconds")
        if policy not in ("skip", "duck_music"):
            raise ValueError("Unsupported announcement busy_policy")
        key = identity + ":" + rid
        # Retain the exact b1 skip fingerprint across upgrades. Only the new
        # policy adds a discriminator, so old retries remain status-only.
        fingerprint = [source, expires_at] if policy == "skip" else [source, expires_at, policy]
        digest = hashlib.sha256(json.dumps(fingerprint, separators=(",", ":")).encode()).hexdigest()
        async with self.lock:
            old = self.records.get(key)
            if old and old["fingerprint"] != digest:
                return failed(rid, "request_id_conflict", status="failed")
        if old:
            return await self.get_status(target, rid)
        now = self.now()
        if not now < expires_at <= now + MAX_DEADLINE:
            return failed(rid, "deadline_out_of_range", status="skipped")
        caps = await self.get_capabilities(target)
        if not all(caps[key] for key in CAPABILITIES):
            return failed(rid, "guarded_endpoint_unavailable", status="skipped")
        if policy == "duck_music" and not caps["duck_music"]:
            return failed(rid, "duck_music_unavailable", status="skipped")
        try:
            url = media_id(await self.resolve(source))
        except Exception:
            return failed(rid, "media_resolution_failed", status="failed")
        if urlsplit(url).scheme not in {"http", "https"}:
            return failed(rid, "media_resolution_failed", status="failed")
        async with self.lock:
            # Two simultaneous requests may have resolved the same media.
            old = self.records.get(key)
            if old and old["fingerprint"] != digest:
                return failed(rid, "request_id_conflict", status="failed")
            if old is None:
                now = self.now()
                if expires_at <= now:
                    return failed(rid, "expired_before_dispatch", status="skipped")
                self.records = {k: v for k, v in self.records.items() if v["expires_at"] + RETENTION > now}
                if len(self.records) >= MAX_RECORDS:
                    return failed(rid, "ledger_full", status="skipped")
                self.records[key] = {"fingerprint": digest, "expires_at": expires_at}
                try:
                    await self.save(dict(self.records))
                except Exception:
                    self.records.pop(key, None)
                    return failed(rid, "ledger_persistence_failed", status="failed")
        if old:
            return await self.get_status(target, rid)
        try:
            result = await self.send(target, "submit_duck" if policy == "duck_music" else "submit", {
                "request_id": rid, "media_id": url, "expires_at": str(expires_at),
            })
            return receipt(result, rid, boot_id=caps["boot_id"])
        except Exception:
            # Never resend: a disconnected transport may have delivered it.
            return failed(rid, "native_submit_unconfirmed")

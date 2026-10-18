"""Opt-in attended recording extension for pinned EchoMuse Controller 2.26.0.

Only an authenticated administrator can arm a session. A physical Dot tap
starts preparation, then a second tap stops the take. No speech recognition.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import wave

RATE = 16000
PREPARE_SECONDS = 8
TAKE_SECONDS = 12
LEASE_SECONDS = 20
SESSION_SECONDS = 600
SESSIONS = {}
ACTIVE = {}


def ring(red=0, green=0, blue=0):
    return [{"id": i, "r": red if i in (0, 6) else 0,
             "g": green if i in (0, 6) else 0,
             "b": blue if i in (0, 6) else 0} for i in range(12)]


class Session:
    def __init__(self, device, core, root, split, count):
        self.device, self.core = device, core
        self.id = uuid.uuid4().hex
        self.root = root / self.id
        self.root.mkdir(parents=True, mode=0o700)
        self.split, self.count = split, count
        self.state, self.error = "armed", ""
        self.takes = []
        self.started = self.heartbeat = time.monotonic()
        self.audio = bytearray()
        self.frames = 0
        self.last_seq = None
        self.last_frame = None
        self.ready_offset = None
        self.task = None
        self.closed = False
        self.finishing = False
        self.gaps = 0
        self.guard = None
        # A completed button press may still be saving in a worker thread
        # when the page closes or its lease expires. Serialize finalization so
        # close cannot clear its audio or let it resurrect a closed session.
        self.finalize_lock = asyncio.Lock()

    def view(self):
        return {"id": self.id, "state": self.state, "error": self.error,
                "phrase": "Привет, Мышка", "split": self.split,
                "count": self.count, "takes": self.takes,
                "next": len(self.takes) + 1, "closed": self.closed}

    async def send(self, message):
        # Device.send_control swallows failures. Recording must fail closed.
        await asyncio.wait_for(self.device.control_ws.send(json.dumps(message)), 3)

    async def light(self, r=0, g=0, b=0):
        await self.send({"type": "leds", "leds": ring(r, g, b), "listening": False})

    async def restore_stream(self):
        effective = await asyncio.to_thread(self.core.db.get_effective_device_config,
                                             self.device.device_id)
        await self.send({"type": "config", **{k: effective[k] for k in
                         ("owwOnDevice", "wakeSound", "bargeInEnabled") if k in effective}})
        await self.send({"type": "mic_stop"})
        if self.device.wake_word_enabled and not self.device.muted:
            await self.send({"type": "mic_start"})

    async def arm(self):
        await self.device.voice_lock.acquire()
        self.device.oww_paused.set()
        self.device.oww_paused_since = time.monotonic()
        self.guard = asyncio.create_task(self.watch())
        try:
            await self.light(20, 12, 0)
        except Exception:
            await self.close("Cannot signal the device")
            raise

    async def watch(self):
        try:
            while not self.closed:
                await asyncio.sleep(.25)
                now = time.monotonic()
                if (now - self.heartbeat > LEASE_SECONDS or
                        now - self.started > SESSION_SECONDS):
                    await self.close("Session expired; incomplete take discarded")
                elif self.core.get_device(self.device.device_id) is not self.device:
                    await self.close("Device reconnected; incomplete take discarded")
                elif self.device.muted:
                    await self.close("Microphone muted; incomplete take discarded")
                elif self.state == "recording" and self.last_frame and now-self.last_frame > 1.5:
                    await self.close("Audio stalled; incomplete take discarded")
        except asyncio.CancelledError:
            # close() owns stream restoration and cancels this lease watcher.
            pass

    def feed(self, pcm, seq):
        if self.state not in ("preparing", "recording") or self.finishing:
            return
        if len(pcm) != 2560:
            self.error = "Unexpected audio frame size"
            return
        if self.last_seq is not None and seq != (self.last_seq + 1) % 65536:
            self.gaps += 1
        self.last_seq = seq
        self.last_frame = time.monotonic()
        self.frames += 1
        if len(self.audio) + len(pcm) <= RATE * 2 * (TAKE_SECONDS + PREPARE_SECONDS + 2):
            self.audio.extend(pcm)

    async def prepare(self):
        self.state, self.error = "preparing", ""
        self.audio.clear()
        self.frames, self.gaps = 0, 0
        self.last_seq = self.last_frame = self.ready_offset = None
        try:
            await self.light(20, 12, 0)
            await self.send({"type": "mic_stop"})
            # Shadow streams exactly the ungated wake frontend; it does not
            # run the speech-turn beam lock/VAD/AGC or trigger the assistant.
            await self.send({"type": "config", "owwOnDevice": "shadow",
                             "wakeSound": False, "bargeInEnabled": False})
            await self.send({"type": "mic_start"})
            deadline = time.monotonic() + PREPARE_SECONDS
            while self.frames < 6:
                if time.monotonic() > deadline or self.error:
                    raise RuntimeError("No stable audio stream; no ready signal was sent")
                await asyncio.sleep(.02)
            if self.gaps:
                raise RuntimeError("Audio frames missing during preparation")
            self.ready_offset = len(self.audio) / (RATE * 2)
            self.state = "recording"
            # Capture was already active for at least 480 ms before this cue.
            for _ in range(2):
                await self.light(0, 100, 180)
                await asyncio.sleep(.15)
                await self.light()
                await asyncio.sleep(.12)
            await self.light(0, 35, 70)
            await asyncio.sleep(TAKE_SECONDS)
            await self.finish("timeout")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = str(exc)
            await self.close(self.error)

    async def tap(self, down):
        if self.closed or self.finishing or down:
            return
        if self.state == "armed":
            self.state = "preparing"
            self.task = asyncio.create_task(self.prepare())
        elif self.state == "recording":
            # Do not block the device's control socket receiving loop.
            self.finishing = True
            asyncio.create_task(self.finish("button"))
        # Preparation taps are ignored: only blue/cyan means ready to speak.

    async def finish(self, reason):
        async with self.finalize_lock:
            await self._finish(reason)

    async def _finish(self, reason):
        if self.closed or self.state != "recording":
            return
        self.finishing = True
        self.state = "saving"
        if self.task and self.task is not asyncio.current_task():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        try:
            await self.restore_stream()
            if reason != "button" or self.gaps or self.error:
                await self._close(self.error or "Take timed out or lost frames; incomplete audio discarded")
                return
            number = len(self.takes) + 1
            path = self.root / f"{number:02d}.wav"
            pcm = bytes(self.audio)
            await asyncio.to_thread(self.write_take, path, pcm)
            raw = path.read_bytes()
            take = {"number": number, "seconds": len(pcm)/(RATE*2),
                    "ready_offset_seconds": self.ready_offset,
                    "sha256": hashlib.sha256(raw).hexdigest(), "frames": self.frames,
                    "gaps": self.gaps, "stop_reason": reason,
                    "split": self.split, "phrase": "Привет, Мышка",
                    "source": "echomuse_ungated_wake_stream", "label": "positive"}
            self.takes.append(take)
            (self.root / f"{number:02d}.json").write_text(json.dumps(take, ensure_ascii=False, indent=2))
            os.chmod(self.root / f"{number:02d}.json", 0o600)
            self.audio.clear()
            await self.light(0, 90, 0)
            await asyncio.sleep(.5)
            if number >= self.count:
                await self._close()
            else:
                self.state = "armed"
                await self.light(20, 12, 0)
        except Exception:
            await self._close("Could not save or restore the take")
        finally:
            self.finishing = False

    def write_take(self, path, pcm):
        with path.open("xb") as f:
            os.chmod(path, 0o600)
            with wave.open(f, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(pcm)

    async def close(self, error=""):
        async with self.finalize_lock:
            await self._close(error)

    async def _close(self, error=""):
        if self.closed:
            return
        self.closed = True
        if error:
            self.error = error
        self.state = "error" if self.error else "complete"
        if self.task and self.task is not asyncio.current_task():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.guard and self.guard is not asyncio.current_task():
            self.guard.cancel()
        try:
            if self.core.get_device(self.device.device_id) is self.device:
                await self.restore_stream()
                await self.light()
        except Exception:
            self.error = self.error or "Device disconnected during restore; reconnect loads saved settings"
            self.state = "error"
        finally:
            self.audio.clear()
            for q in (self.device.voice_queue, self.device.mic_queue):
                while not q.empty():
                    q.get_nowait()
            self.device.oww_paused.clear()
            self.device.oww_paused_since = None
            self.device.voice_lock.release()
            ACTIVE.pop(self.device.device_id, None)


def feed(device, pcm, seq):
    session = ACTIVE.get(device.device_id)
    if session:
        session.feed(pcm, seq)
        return True
    return False


async def button(device, event):
    session = ACTIVE.get(device.device_id)
    if session and event.get("clickType") == 138:
        await session.tap(event.get("down", True))
        return True
    return False


def active(device):
    return device.device_id in ACTIVE


def install(app, api):
    from aiohttp import web
    import em_auth
    import sys
    core = sys.modules.get("__main__")
    if not hasattr(core, "get_device"):
        raise RuntimeError("Training extension requires the pinned controller entrypoint")
    root = Path(os.environ.get("DB_PATH", "/app/data/echomuse.db")).parent / "training-recordings"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)

    @em_auth.require_admin
    async def create(request):
        body = await request.json()
        split, count = body.get("split", "train"), body.get("count", 12)
        if split not in ("train", "val", "test") or type(count) is not int or not 1 <= count <= 24:
            raise web.HTTPBadRequest(text="Invalid split/count")
        d = core.get_device(request.match_info["device"])
        if d is None or d.data_ws is None:
            raise web.HTTPConflict(text="Device is not connected")
        if (d.device_id in ACTIVE or d.voice_lock.locked() or d.muted or
                d.speaking or d.listening or d.timer_alarm_task is not None or core.em_player.is_playing(d.device_id)):
            raise web.HTTPConflict(text="Device is busy, muted, playing music or already armed")
        s = Session(d, core, root, split, count)
        # Reserve before awaiting: two simultaneous requests cannot arm it.
        ACTIVE[d.device_id] = s
        SESSIONS[s.id] = s
        for key, old in list(SESSIONS.items()):
            if old.closed and time.monotonic()-old.started > 3600:
                del SESSIONS[key]
        await s.arm()
        return web.json_response(s.view())

    def lookup(request):
        s = SESSIONS.get(request.match_info["session"])
        if s is None:
            raise web.HTTPNotFound()
        return s

    @em_auth.require_admin
    async def status(request):
        s = lookup(request)
        return web.json_response(s.view())

    @em_auth.require_admin
    async def heartbeat(request):
        s = lookup(request)
        s.heartbeat = time.monotonic()
        return web.json_response(s.view())

    @em_auth.require_admin
    async def tap(request):
        s = lookup(request)
        await s.tap(False)
        return web.json_response(s.view())

    @em_auth.require_admin
    async def close(request):
        s = lookup(request)
        await s.close("Stopped by operator")
        return web.json_response(s.view())

    @em_auth.require_admin
    async def audio(request):
        s = lookup(request)
        try:
            n = int(request.match_info["take"])
        except ValueError:
            raise web.HTTPNotFound() from None
        if not 1 <= n <= len(s.takes):
            raise web.HTTPNotFound()
        return web.FileResponse(s.root / f"{n:02d}.wav")

    app.router.add_post("/api/training/devices/{device}/sessions", create)
    app.router.add_get("/api/training/sessions/{session}", status)
    app.router.add_post("/api/training/sessions/{session}/heartbeat", heartbeat)
    app.router.add_post("/api/training/sessions/{session}/tap", tap)
    app.router.add_post("/api/training/sessions/{session}/close", close)
    app.router.add_get("/api/training/sessions/{session}/takes/{take}", audio)

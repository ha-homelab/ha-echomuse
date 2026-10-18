"""Behaviour tests with fake audio and device sockets; never open a microphone."""
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('training_recorder', ROOT/'training/recorder/controller.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Socket:
    def __init__(self):
        self.sent = []
    async def send(self, data):
        self.sent.append(json.loads(data))


class RecorderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.d = types.SimpleNamespace(device_id='test', control_ws=Socket(),
            voice_lock=asyncio.Lock(), oww_paused=asyncio.Event(), oww_paused_since=None,
            muted=False, wake_word_enabled=True, voice_queue=asyncio.Queue(), mic_queue=asyncio.Queue())
        config={'owwOnDevice':'on','wakeSound':True,'bargeInEnabled':True}
        self.core = types.SimpleNamespace(get_device=lambda _:self.d,
            db=types.SimpleNamespace(get_effective_device_config=lambda _:config))
        self.s = m.Session(self.d,self.core,Path(self.temp.name),'train',2)
        m.ACTIVE['test']=self.s
        await self.s.arm()

    async def asyncTearDown(self):
        if not self.s.closed:
            await self.s.close()
        self.temp.cleanup()
        m.ACTIVE.clear()

    async def ready(self):
        await self.s.tap(False)
        await asyncio.sleep(.01)
        self.assertFalse(any(x.get('leds')==m.ring(0,100,180) for x in self.d.control_ws.sent))
        for n in range(6):
            m.feed(self.d,bytes(2560),n)
        await asyncio.sleep(.04)
        self.assertEqual(self.s.state,'recording')

    async def test_no_audio_before_tap_ready_after_frames_and_stop_saves(self):
        self.assertFalse(any(x['type']=='mic_start' for x in self.d.control_ws.sent))
        m.feed(self.d,bytes(2560),0)
        self.assertEqual(len(self.s.audio),0)
        await self.ready()
        self.assertEqual(self.s.ready_offset,.48)
        m.feed(self.d,bytes(2560),6)
        await m.button(self.d,{'clickType':138,'down':False})
        await asyncio.sleep(.6)
        self.assertEqual(self.s.state,'armed')
        self.assertEqual(len(self.s.takes),1)
        self.assertEqual(self.s.takes[0]['frames'],7)
        self.assertEqual(self.s.takes[0]['split'],'train')
        self.assertTrue((self.s.root/'01.wav').exists())
        self.assertEqual(self.s.audio,bytearray())
        self.assertTrue(self.d.voice_lock.locked())
        self.assertTrue(any(x.get('owwOnDevice')=='on' for x in self.d.control_ws.sent))

    async def test_failed_preparation_never_signals_ready(self):
        old=m.PREPARE_SECONDS;m.PREPARE_SECONDS=.01
        try:
            await self.s.tap(False)
            await asyncio.sleep(.1)
            self.assertTrue(self.s.closed)
            self.assertFalse(self.s.takes)
            self.assertFalse(any(x.get('leds')==m.ring(0,100,180) for x in self.d.control_ws.sent))
            self.assertFalse(self.d.voice_lock.locked())
        finally:m.PREPARE_SECONDS=old

    async def test_lost_frames_discard_take(self):
        await self.ready()
        m.feed(self.d,bytes(2560),8)
        await m.button(self.d,{'clickType':138,'down':False})
        await asyncio.sleep(.05)
        self.assertTrue(self.s.closed)
        self.assertFalse(self.s.takes)
        self.assertFalse(list(self.s.root.glob('*.wav')))

    async def test_page_lease_closes_and_restores(self):
        self.s.heartbeat-=m.LEASE_SECONDS+1
        await asyncio.sleep(.3)
        self.assertTrue(self.s.closed)
        self.assertFalse(self.d.voice_lock.locked())
        self.assertFalse(self.d.oww_paused.is_set())
        self.assertNotIn('test',m.ACTIVE)

    async def test_timeout_is_not_a_labelled_take(self):
        await self.ready()
        await self.s.finish('timeout')
        self.assertFalse(self.s.takes)
        self.assertTrue(self.s.closed)

    async def test_mute_aborts(self):
        await self.ready()
        self.d.muted=True
        await asyncio.sleep(.3)
        self.assertTrue(self.s.closed)
        self.assertFalse(self.s.takes)

    async def test_button_down_and_other_buttons_do_not_save(self):
        self.assertFalse(await m.button(self.d,{'clickType':999,'down':False}))
        await m.button(self.d,{'clickType':138,'down':True})
        self.assertEqual(self.s.state,'armed')

    async def test_close_during_save_preserves_take_and_cannot_rearm(self):
        await self.ready()
        started, release = threading.Event(), threading.Event()
        original = self.s.write_take

        def delayed_write(path, pcm):
            started.set()
            if not release.wait(3):
                raise RuntimeError('Test writer was not released')
            original(path, pcm)

        self.s.write_take = delayed_write
        expected_pcm = bytes(self.s.audio)
        saving = asyncio.create_task(self.s.finish('button'))
        closing = None
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            closing = asyncio.create_task(self.s.close('Stopped by operator'))
            await asyncio.sleep(.02)
            self.assertFalse(closing.done())
            release.set()
            await asyncio.wait_for(asyncio.gather(saving, closing), 2)
        finally:
            release.set()
            await asyncio.gather(saving, *([closing] if closing else []), return_exceptions=True)
        self.assertTrue(self.s.closed)
        self.assertEqual(self.s.state, 'error')
        self.assertEqual(len(self.s.takes), 1)
        with wave.open(str(self.s.root/'01.wav'), 'rb') as audio:
            self.assertEqual(audio.readframes(audio.getnframes()), expected_pcm)
        self.assertEqual(self.s.takes[0]['seconds'], len(expected_pcm)/(m.RATE*2))
        self.assertFalse(self.d.voice_lock.locked())
        self.assertNotIn('test', m.ACTIVE)

    async def test_close_before_scheduled_finish_discards_incomplete_take(self):
        await self.ready()
        await self.s.close('Stopped by operator')
        await self.s.finish('button')
        self.assertTrue(self.s.closed)
        self.assertEqual(self.s.state, 'error')
        self.assertFalse(self.s.takes)
        self.assertFalse(list(self.s.root.glob('*.wav')))


class ImportTests(unittest.TestCase):
    def test_incomplete_session_rejected(self):
        import_spec = importlib.util.spec_from_file_location('import_recording', ROOT/'training/recorder/import_session.py')
        module = importlib.util.module_from_spec(import_spec)
        import_spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'session.json').write_text(json.dumps({'state':'armed','takes':[],'count':12}))
            with self.assertRaisesRegex(ValueError, 'completed'):
                module.import_session(root, [])

    def test_completed_history_does_not_resume_or_contact_device(self):
        spec = importlib.util.spec_from_file_location('local_recorder', ROOT/'training/recorder/local_server.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            creds = root/'credentials.json'
            creds.write_text(json.dumps({'url':'http://invalid.example'}))
            app = module.App(types.SimpleNamespace(credentials=creds, output=root/'recordings'))
            def unexpected_request(*args, **kwargs):
                raise AssertionError('History must not contact the controller')
            app.request = unexpected_request
            folder = app.output/'complete'; folder.mkdir()
            (folder/'01.wav').write_bytes(b'placeholder')
            (folder/'session.json').write_text(json.dumps({
                'state':'complete','closed':True,'count':1,'takes':[{'number':1}]}))
            self.assertEqual(app.action('history', {})['saved_on_mac'], 1)
            self.assertIsNone(app.session)
            app.session = {'closed':False}
            self.assertIsNone(app.action('history', {}))
            app.session = {'id':'current', 'closed':False}
            with self.assertRaisesRegex(ValueError, 'different session'):
                app.action('close', {'session_id':'stale'})
            with self.assertRaisesRegex(ValueError, 'different session'):
                app.action('tap', {'session_id':'stale'})


if __name__=='__main__':unittest.main()

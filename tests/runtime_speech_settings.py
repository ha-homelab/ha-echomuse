"""Exercise settings config flow and entities in an isolated HA runtime."""
import asyncio
import copy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from custom_components.russian_speech_settings.client import SettingsError

DEFAULTS = dict(voice='silero-ru-baya', rate=100, pitch=0, sentence_pause_ms=0,
                intonation='auto', emphasis_words='', emphasis_intensity=3,
                auto_stress=True, auto_yo=True)
SCHEMA = {
    'voice': {'type':'select','options':['silero-ru-baya','silero-ru-kseniya','silero-ru-xenia','silero-ru-aidar','silero-ru-eugene']},
    'intonation': {'type':'select','options':['auto','statement','question','exclamation']},
    'rate': {'type':'number','min':80,'max':130,'step':1,'unit':'%'},
    'pitch': {'type':'number','min':-10,'max':10,'step':1,'unit':'%'},
    'sentence_pause_ms': {'type':'number','min':0,'max':1000,'step':50,'unit':'ms'},
    'emphasis_intensity': {'type':'number','min':1,'max':3,'step':1},
    'emphasis_words': {'type':'text','max':160},
    'auto_stress': {'type':'switch'}, 'auto_yo': {'type':'switch'},
}

class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='speech-settings-test-')
        self.addCleanup(self.tmp.cleanup)
        shutil.copytree(ROOT/'custom_components/russian_speech_settings', Path(self.tmp.name)/'custom_components/russian_speech_settings')
        self.hass = HomeAssistant(self.tmp.name)
        loader.async_setup(self.hass)
        self.hass.config_entries = ConfigEntries(self.hass, {})
        self.hass.config.skip_pip = True
        self.assertTrue(await async_load_base_functionality(self.hass))
        self.data = dict(version=1, backend='silero', model='v5_6_ru', persistent=True,
                         settings=dict(DEFAULTS), defaults=dict(DEFAULTS), schema=SCHEMA)
        self.fail = False
        self.patches = []
        self.cache = AsyncMock()
        self.hass.services.async_register('tts','clear_cache',self.cache)
        async def request(client, patch=None):
            if self.fail:
                raise SettingsError('Fixture unavailable')
            if patch is not None:
                self.patches.append(patch)
                self.data['settings'].update(patch)
            return copy.deepcopy(self.data)
        self.addCleanup(patch.stopall)
        patch('custom_components.russian_speech_settings.client.Client.request', request).start()
        patch('custom_components.russian_speech_settings.async_get_clientsession', return_value=None).start()
        patch('custom_components.russian_speech_settings.config_flow.async_get_clientsession', return_value=None).start()
        options = ('https://speech.local:8093','test-'+'x'*40,None)
        patch('custom_components.russian_speech_settings.connection_options',return_value=options).start()
        patch('custom_components.russian_speech_settings.config_flow.connection_options',return_value=options).start()
        result = await self.hass.config_entries.flow.async_init('russian_speech_settings',context={'source':'user'},data={
            'endpoint': options[0], 'token': options[1], 'ca_file':'/unused/ca.crt'})
        self.assertEqual(result['type'],'create_entry',result)
        self.entry = result['result']
        await self.hass.async_block_till_done()
        await self.hass.async_start()
        await self.hass.async_block_till_done()

    async def asyncTearDown(self):
        await self.hass.async_stop(force=True)

    def entity(self, suffix):
        from homeassistant.helpers import entity_registry as er
        return next(e.entity_id for e in er.async_get(self.hass).entities.values()
                    if e.config_entry_id==self.entry.entry_id and e.unique_id==self.entry.entry_id+'_'+suffix)

    async def test_controls_persistence_source_cache_and_unload(self):
        self.assertEqual(len([s for s in self.hass.states.async_all() if 'local_russian_speech' in s.entity_id]),10)
        voice = self.entity('voice')
        self.assertEqual(len(self.hass.states.get(voice).attributes['options']),5)
        await self.hass.services.async_call('select','select_option',{'entity_id':voice,'option':'silero-ru-xenia'},blocking=True)
        self.assertEqual(self.data['settings']['voice'],'silero-ru-xenia')
        self.assertEqual(self.patches[-1],{'voice':'silero-ru-xenia'})
        self.cache.assert_awaited_once()
        await self.hass.services.async_call('number','set_value',{'entity_id':self.entity('rate'),'value':110},blocking=True)
        await self.hass.services.async_call('switch','turn_off',{'entity_id':self.entity('auto_yo')},blocking=True)
        await self.hass.services.async_call('text','set_value',{'entity_id':self.entity('emphasis_words'),'value':'батарея, готова'},blocking=True)
        self.assertEqual(self.hass.states.get(self.entity('rate')).state,'110')
        await self.hass.services.async_call('button','press',{'entity_id':self.entity('reset')},blocking=True)
        self.assertEqual(self.data['settings'],DEFAULTS)
        self.assertTrue(await self.hass.config_entries.async_unload(self.entry.entry_id))

    async def test_failed_write_not_optimistic_and_external_change_refresh(self):
        self.fail = True
        with self.assertRaises(HomeAssistantError):
            await self.hass.services.async_call('number','set_value',{'entity_id':self.entity('rate'),'value':120},blocking=True)
        self.assertEqual(self.hass.states.get(self.entity('rate')).state,'100')
        self.fail = False
        self.data['settings']['rate'] = 115
        await self.entry.runtime_data.async_refresh()
        self.assertEqual(self.hass.states.get(self.entity('rate')).state,'115')
        self.cache.assert_awaited_once()

if __name__=='__main__':
    unittest.main()

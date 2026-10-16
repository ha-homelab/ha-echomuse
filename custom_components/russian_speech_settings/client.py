"""Small CA-verified client; no text or audio is sent by these controls."""
import ipaddress
import json
from pathlib import Path
import ssl
from urllib.parse import urlsplit

import aiohttp


class SettingsError(Exception):
    """A fixed error category which never contains credentials or server payloads."""


class AuthenticationError(SettingsError):
    """The service rejected the credential."""


def connection_options(data):
    endpoint = data['endpoint'].rstrip('/')
    url = urlsplit(endpoint)
    host = url.hostname or ''
    try:
        address = ipaddress.ip_address(host)
        private = address.is_private and not address.is_unspecified and not address.is_multicast
    except ValueError:
        private = host == 'localhost' or host.endswith(('.local', '.internal', '.svc.cluster.local'))
    if (url.scheme != 'https' or not private or url.path or url.query or url.fragment
            or url.username or url.password or not url.port):
        raise ValueError('Use the private HTTPS service origin including its port')
    token = data['token']
    if len(token) < 32 or any(c.isspace() for c in token):
        raise ValueError('Invalid credential')
    if not Path(data['ca_file']).is_absolute():
        raise ValueError('Use an absolute CA file path')
    context = ssl.create_default_context(cafile=data['ca_file'])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.hostname_checks_common_name = False
    return endpoint, token, context


class Client:
    def __init__(self, session, options):
        self.session = session
        self.endpoint, self.token, self.context = options

    async def request(self, patch=None):
        try:
            async with self.session.request(
                'GET' if patch is None else 'PATCH', self.endpoint + '/v1/settings',
                json=patch, headers={'Authorization': 'Bearer ' + self.token},
                ssl=self.context, allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as response:
                if response.status in (401, 403):
                    raise AuthenticationError('Authentication failed')
                if response.status != 200:
                    raise SettingsError('Settings request failed')
                raw = bytearray()
                async for chunk in response.content.iter_chunked(4096):
                    raw.extend(chunk)
                    if len(raw) > 16384:
                        raise SettingsError('Oversized settings response')
                data = json.loads(raw)
                if (not isinstance(data, dict) or data.get('version') != 1 or data.get('backend') != 'silero'
                        or not isinstance(data.get('settings'), dict)
                        or not isinstance(data.get('defaults'), dict)
                        or not isinstance(data.get('schema'), dict)):
                    raise SettingsError('Unsupported settings service')
                keys = {'voice', 'rate', 'pitch', 'sentence_pause_ms', 'intonation',
                        'emphasis_words', 'emphasis_intensity', 'auto_stress', 'auto_yo'}
                if not all(keys <= data[name].keys() for name in ('settings', 'defaults', 'schema')):
                    raise SettingsError('Incomplete settings service')
                return data
        except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, TypeError):
            raise SettingsError('Cannot reach settings service') from None

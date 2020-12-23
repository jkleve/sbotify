import discord
import os
import json
import re
import requests
from base64 import b64encode
from datetime import datetime
from urllib.parse import urlparse


__author__ = 'jesse kleve'
__version__ = '0.4.0-dev'


class InitializationException(Exception):
    pass


def get_time():
    return datetime.utcnow().strftime('%y-%m-%d %H:%M:%S')


def handle_log(msg):
    print(f'{get_time()} | {msg}')


def log(msg):
    handle_log(f' info | {msg}')


def log_trace(msg):
    pass


def log_debug(msg):
    handle_log(f'  dbg | {msg}')


def log_error(msg):
    handle_log(f'ERROR | {msg}')


class Spotify(object):
    """
    Handles any link posted containing 'spotify' in the netloc.
    It then tries to parse for a track ID and post that to the
    configured spotify playlist.
    """
    class OAuthMgr(object):
        """Manages the OAuth for Spotify"""
        def __init__(self):
            self.cfg = {
                'file': 'spotify.json',
            }
            self.access = self.load_access()
            self.refresh_session()

        @property
        def access_token(self):
            return self.access["access_token"]

        @property
        def refresh_token(self):
            return self.access["refresh_token"]

        def load_access(self):
            if not os.path.isfile(self.cfg['file']):
                raise InitializationException(f'no access file {self.cfg["file"]}')

            with open(self.cfg['file']) as f:
                return json.loads(f.read())

        def save_access(self):
            with open(self.cfg['file'], 'w') as f:
                f.write(json.dumps(self.access))
            os.chmod(self.cfg['file'], 0o600)

        def refresh_session(self):
            log('refreshing access token')
            encoded_secrets = b64encode(
                f'{os.getenv("SPOTIFY_CLIENT_ID")}:{os.getenv("SPOTIFY_CLIENT_SECRET")}'.encode('utf8')).decode('utf8')
            response = requests.post(
                'https://accounts.spotify.com/api/token',
                headers={'Authorization': f'Basic {encoded_secrets}'},
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': self.access['refresh_token'],
                })

            if response.status_code == requests.codes.ok:
                self.access.update(json.loads(response.text))
                self.save_access()

    def __init__(self):
        self.oauth = self.OAuthMgr()

    async def handle(self, message, url):
        if 'spotify' in url.netloc:
            track_id = self.get_track_id(url)
            if track_id:
                self.add_to_playlist(self.get_playlist_id(message), f'spotify:track:{track_id}')

    @staticmethod
    def get_playlist_id(message):
        return '4QykfvrUZBqnVoO5q6MrSU'

    @staticmethod
    def get_track_id(url):
        """Get base-62 encoded track ID"""
        m = re.search('/track/(?P<track_id>[a-zA-Z0-9]+)$', url.path)
        try:
            return m.group('track_id')
        except IndexError:
            log(f'{url.path} does not appear to be a spotify track')

    def refresh_access_and_add(self, playlist_id, track_uri):
        self.oauth.refresh_session()
        self.add_to_playlist(playlist_id, track_uri)

    def add_to_playlist(self, playlist_id, track_uri):
        log(f'add {track_uri} to spotify:playlist:{playlist_id}')
        response = requests.post(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                                 headers={'Authorization': f'Bearer {self.oauth.access_token}'},
                                 params={'uris': track_uri})

        if response.status_code == requests.codes.unauthorized:
            self.refresh_access_and_add(playlist_id, track_uri)
        elif response.status_code != requests.codes.created:
            log_error(f'failed to add tracks {track_uri}')
            log(response.text)


class Billboard(object):
    """
    Any url link with a hostname (netloc) that contains the name of a discord
    channel under a category is posted to that 'billboard'.

    e.g.
    If there's a channel named 'spotify' in the 'links' category, any url like
    https://open.spotify.com/track/as289zwe02 posted in any channel will be posted
    to the 'spotify' channel.
    """
    def __init__(self):
        pass

    async def handle(self, message, url):
        for category in message.guild.categories:
            if category.name == 'links':
                for channel in category.channels:
                    if channel.name in url.netloc:
                        msg = f'{message.author.display_name} shared {url.geturl()}'
                        await channel.send(msg)
                        log_debug(f'repost {url} to {message.guild.name}:{channel.name}')


class UrlHandlers(object):
    """
    Manages all handlers that want events related to any time someone
    posts a link in a channel
    """
    def __init__(self, handlers=None):
        if handlers is None:
            self.handlers = list()
        elif isinstance(handlers, list):
            self.handlers = handlers
        else:
            self.handlers = (handlers, )

    async def handle(self, message):
        urls = self.get_urls(message.content)
        for url in urls:
            u = urlparse(url)
            for handler in self.handlers:
                await handler.handle(message, u)

    @staticmethod
    def get_urls(string):
        regex = re.compile(r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|
                           (\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))""",
                           re.VERBOSE)
        url = regex.findall(string)
        return [u[0] for u in url]


class Bot(object):
    @staticmethod
    def banner():
        return f"""begin botting
         _           _   _  __
        | |         | | (_)/ _|
     ___| |__   ___ | |_ _| |_ _   _
    / __| '_ \\ / _ \\| __| |  _| | | |
    \\__ \\ |_) | (_) | |_| | | | |_| |
    |___/_.__/ \\___/ \\__|_|_|  \\__, |
                                __/ |
                               |___/    {__version__}
        """

    @staticmethod
    def check_env_vars():
        required_env_vars = (
            'DISCORD_TOKEN',
            'SPOTIFY_CLIENT_ID',
            'SPOTIFY_CLIENT_SECRET',
        )
        for env_var in required_env_vars:
            if not os.getenv(env_var):
                log_error(f'missing environment variable {env_var}')
                exit(1)

    def __init__(self):
        log(self.banner())
        self.check_env_vars()

        url_handlers = UrlHandlers([
            Spotify(),
            Billboard(),
        ])

        client = discord.Client()

        @client.event
        async def on_message(message):
            if message.author == client.user:
                return

            log_trace(f'from {message.author.display_name}: {message.content}')
            for handler in (url_handlers,):
                await handler.handle(message)

        if not os.getenv('NO_START'):
            client.run(os.getenv('DISCORD_TOKEN'))


# @todo main list
# [ ] - log to file (supervisord?)
# [ ] - aiohttp
# [ ] - async & await (almost always use them?)
# [ ] - test refresh_token flow
# [ ] - add a request history and on startup check this list against what's in the chat. send requests if needed.
#       - i thought instead maybe a 'lock' like file that any 201 response on POST /playlists, write that link to a file.
#         then check this file for if the most recent posts were sent to the playlist.
# [ ] - add a check against the playlist's items and on startup check this list against what's in the chat. send requests if needed.
# [ ] - add different channels to different playlists (multi-channel -> respective playlist support)


Bot()

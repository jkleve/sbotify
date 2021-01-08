import discord
import os
import logging
import json
import pytz
import re
import requests
from base64 import b64encode
from datetime import datetime, timedelta
from urllib.parse import urlparse


__author__ = 'Jesse Kleve'
__version__ = '0.7.0'

logging.basicConfig(
    filename='sbotify.log', level=logging.INFO,
    datefmt='%y-%m-%d %H:%M:%S', format='%(asctime)s | %(levelname)5s | %(message)s')
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('discord').setLevel(logging.CRITICAL)


class InitializationException(Exception):
    pass


def log(msg):
    logging.info(msg)


def log_trace(msg):
    pass


def log_debug(msg):
    logging.debug(msg)


def log_error(msg):
    logging.error(msg)


class Spotify(object):
    """
    Handles any link posted containing 'spotify' in the netloc.
    It then tries to parse for a track ID and post that to the
    configured spotify playlist.
    """
    class User(object):
        def __init__(self, user_id):
            self.user_id = user_id

    class OAuthMgr(object):
        """Manages the OAuth for Spotify"""
        def __init__(self):
            self.cfg = {
                'file': 'spotify.json',
            }

            self.access = self.load_access()
            self.refreshed_at = None

            self.refresh_session()

        @property
        def access_token(self):
            return self.access["access_token"]

        @property
        def refresh_token(self):
            return self.access["refresh_token"]

        def is_expired(self):
            # last refresh + expiration + 60 second buffer
            return self.refreshed_at + timedelta(seconds=self.access["expires_in"] + 60) > datetime.utcnow()

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
                log('got new access token')
                self.access.update(json.loads(response.text))
                self.refreshed_at = datetime.utcnow()
                self.save_access()
            else:
                log_error(f'failed to refresh access token: {response.text}')

    class Playlists(object):
        def __init__(self, oauth, user):
            self.oauth = oauth
            self.user = user
            self.playlists = self.refresh_playlists()

        def get_playlist(self, name):
            if name in self.playlists.keys():
                return self.playlists[name]

        @staticmethod
        def parse_playlist_page(response):
            playlists = dict()
            for item in response.json()["items"]:
                playlists[item["name"]] = item["id"]
            return playlists, response.json()["next"]

        def refresh_playlists(self):
            playlists = dict()
            response = requests.get(f'https://api.spotify.com/v1/me/playlists',
                                    headers={'Authorization': f'Bearer {self.oauth.access_token}'},
                                    params={'limit': 50})
            while True:
                if response.ok:
                    items, next_url = self.parse_playlist_page(response)
                    playlists.update(items)
                    if next_url is not None:
                        response = requests.get(response.json()["next"],
                                                headers={'Authorization': f'Bearer {self.oauth.access_token}'})
                    else:
                        break
            return playlists

        def create_playlist(self, name):
            response = requests.post(f'https://api.spotify.com/v1/users/{self.user.user_id}/playlists',
                                     headers={'Authorization': f'Bearer {self.oauth.access_token}'},
                                     json={'name': name})
            if response.ok:
                self.playlists = self.refresh_playlists()
                return self.get_playlist(name)

    def __init__(self):
        self.oauth = self.OAuthMgr()
        self.playlists = self.Playlists(self.oauth, Spotify.User('1234133441'))

    async def handle(self, message, url):
        if 'spotify' in url.netloc:
            track_id = self.get_track_id(url)
            if track_id:
                self.add_to_playlist(await self.get_playlist_id(message), f'spotify:track:{track_id}')

    async def get_playlist_id(self, message):
        playlist_name = f'400% Fuego {datetime.now(pytz.timezone("US/Central")).strftime("%B")}'
        playlist_id = self.playlists.get_playlist(playlist_name)
        if playlist_id is None:
            playlist_id = self.playlists.create_playlist(playlist_name)
            await message.channel.send(f'Created new playlist {playlist_name} '
                                       f'https://open.spotify.com/playlist/{playlist_id}')
        return playlist_id

    @staticmethod
    def get_track_id(url):
        """Get base-62 encoded track ID"""
        m = re.search('/track/(?P<track_id>[a-zA-Z0-9]+)$', url.path)
        if not m:
            log(f'{url.path} does not appear to be a spotify track')
        else:
            try:
                return m.group('track_id')
            except IndexError:
                log(f'{url.path} does not appear to be a spotify track')

    def add_to_playlist(self, playlist_id, track_uri):
        log(f'add {track_uri} to spotify:playlist:{playlist_id}')
        response = requests.post(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                                 headers={'Authorization': f'Bearer {self.oauth.access_token}'},
                                 params={'uris': track_uri})

        if response.ok:
            log(f'added {track_uri} to {playlist_id}')
        else:
            log_error(f'failed to add tracks {track_uri}: {response.text}')


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
        posted = False
        other_channel = None
        for category in message.guild.categories:
            if category.name == 'links':
                msg = f'{message.author.display_name} shared {url.geturl()}'
                for channel in category.channels:
                    if channel.name in url.netloc:
                        await channel.send(msg)
                        log(f'billboard {url.geturl()} to {message.guild.name}:{channel.name}')
                        posted = True
                    if channel.name == 'other':
                        other_channel = channel
                if not posted and other_channel is not None:
                    await other_channel.send(msg)
                    log(f'billboard {url.geturl()} to {message.guild.name}:{other_channel.name}')


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

            if os.getenv('TEST') and message.guild.name != 'test':
                return

            log_trace(f'from {message.author.display_name}: {message.content}')
            for handler in [url_handlers, ]:
                await handler.handle(message)

        if not os.getenv('NO_START'):
            client.run(os.getenv('DISCORD_TOKEN'))


# @todo main list
# [ ] - sbotify.dori.llc (switch to google?)
# [ ] - dockererize (docker-compose)
# [ ] - aiohttp
# [ ] - async & await (almost always use them?)
# [ ] - add a request history and on startup check this list against what's in the chat. send requests if needed.
#       - i thought instead maybe a 'lock' like file that any 201 response on POST /playlists, write that link to a file.
#         then check this file for if the most recent posts were sent to the playlist.
# [ ] - add a check against the playlist's items and on startup check this list against what's in the chat. send requests if needed.
# [ ] - add different channels to different playlists (multi-channel -> respective playlist support)

# things to test on release
# [ ] - refresh_token flow


Bot()

import json
import os
import re
import pytz
import requests
from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import logger
from . import InitializationException


def get_track_id(url):
    """Get base-62 encoded track ID"""
    match = re.search('/track/(?P<track_id>[a-zA-Z0-9]+)$', url.path)
    if not match:
        logger.info(f'{url.path} does not appear to be a spotify track')
    else:
        try:
            return match.group('track_id')
        except IndexError:
            logger.info(f'{url.path} does not appear to be a spotify track')


@dataclass
class SpotifyUser(object):
    user_id: int


class SpotifyOauthManager(object):
    """Manages the OAuth for Spotify"""
    def __init__(self):
        self.cfg = {
            'file': 'spotify.json',
        }
    
        self.access = self._load_access()
        self.refreshed_at = None
    
        self.refresh_session()
    
    @property
    def access_token(self):
        return self.access["access_token"]
    
    def is_expired(self):
        # last refresh + expiration + 60 second buffer
        return datetime.utcnow() > self.refreshed_at + timedelta(seconds=self.access["expires_in"] + 60)
    
    def _load_access(self):
        if not os.path.isfile(self.cfg['file']):
            raise InitializationException(f'no access file {self.cfg["file"]}')
    
        with open(self.cfg['file']) as f:
            return json.loads(f.read())
    
    def _save_access(self):
        with open(self.cfg['file'], 'w') as f:
            f.write(json.dumps(self.access))
        os.chmod(self.cfg['file'], 0o600)
    
    def refresh_session(self):
        logger.info('refreshing access token')
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
            logger.info('got new access token')
            self.access.update(json.loads(response.text))
            self.refreshed_at = datetime.utcnow()
            self._save_access()
        else:
            logger.error(f'failed to refresh access token: {response.text}')


class SpotifyPlaylist(object):
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


class Spotify(object):
    def __init__(self):
        for env_var in ['SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET']:
            if env_var not in os.environ:
                raise InitializationException(f'{env_var} not set')

        self._oauth = SpotifyOauthManager()
        self._playlists = SpotifyPlaylist(self._oauth, SpotifyUser(SpotifyUser("1234133441")))

    async def handle(self, message, url) -> bool:
        if 'spotify' in url.netloc:
            if self.oauth.is_expired():
                self.oauth.refresh_session()
            track_id = self.get_track_id(url)
            if track_id:
                return self.add_to_playlist(await self.get_playlist_id(message), f'spotify:track:{track_id}')

    async def get_playlist_id(self, message):
        playlist_name = f'400% Fuego {datetime.now(pytz.timezone("US/Central")).strftime("%B")}'
        playlist_id = self.playlists.get_playlist(playlist_name)
        if playlist_id is None:
            playlist_id = self.playlists.create_playlist(playlist_name)
            await message.channel.send(f'Created new playlist {playlist_name} '
                                       f'https://open.spotify.com/playlist/{playlist_id}')
        return playlist_id

    def add_to_playlist(self, playlist_id, track_uri) -> bool:
        logger.info(f'add {track_uri} to spotify:playlist:{playlist_id}')
        response = requests.post(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                                 headers={'Authorization': f'Bearer {self.oauth.access_token}'},
                                 params={'uris': track_uri})

        if response.ok:
            logger.info(f'added {track_uri} to {playlist_id}')
        else:
            logger.error(f'failed to add tracks {track_uri}: {response.text}')
        return response.ok

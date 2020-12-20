import discord
import os
import json
import re
import requests
from base64 import b64encode
from datetime import datetime
from urllib.parse import urlparse


__author__ = 'jesse kleve'
__version__ = '0.1.0'


def get_time():
    return datetime.utcnow().strftime('%y-%m-%d %H:%M:%S')


def log(msg):
    print(f'{get_time()} | {msg}')


def log_error(msg):
    print(f'{get_time()} | ERROR - {msg}')


def get_refresh_token():
    creds_file = 'creds.json'

    # create file
    if not os.path.isfile(creds_file):
        return None

    with open('creds.json') as f:
        try:
            return json.loads(f.read())["refresh_token"]
        except KeyError:
            pass


def save_access(access):
    creds_file = 'creds.json'
    with open(creds_file, 'w') as f:
        f.write(access)
    os.chmod(creds_file, 0o600)


def get_login_code():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    redirect_uri = 'http%3A%2F%2Flocalhost%3A5000'
    scope = 'playlist-modify-public'  # space delimited

    log('login required')
    log(f' https://accounts.spotify.com/authorize?'
        f'response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}')
    log('what is the code?')
    return input()


def send_auth_code(code):
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    encoded_secrets = b64encode(f'{client_id}:{client_secret}'.encode('utf8')).decode('utf8')
    response = requests.post(
        'https://accounts.spotify.com/api/token',
        headers={'Authorization': f'Basic {encoded_secrets}'},
        data={
            'grant_type': 'authorization_code',
            'redirect_uri': 'http://localhost:5000',
            'code': code,
        })

    if response.status_code == requests.codes.ok:
        return json.loads(response.text)
    else:
        log(f'{response.status_code}')
        log(f'{response.text}')


def send_refresh_token(refresh_token):
    log('refreshing access token')
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    encoded_secrets = b64encode(f'{client_id}:{client_secret}'.encode('utf8')).decode('utf8')
    response = requests.post(
        'https://accounts.spotify.com/api/token',
        headers={'Authorization': f'Basic {encoded_secrets}'},
        data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        })

    if response.status_code == requests.codes.ok:
        return json.loads(response.text)


def login():
    refresh_token = get_refresh_token()
    if refresh_token is None:
        code = get_login_code()
        access = send_auth_code(code)
    else:
        access = send_refresh_token(refresh_token)
    return access


class Bot:
    class LoginError(Exception):
        pass

    def __init__(self):
        self.access = login()
        self.playlist_id = '4QykfvrUZBqnVoO5q6MrSU'

        if self.access is None:
            raise self.LoginError
        else:
            save_access(json.dumps(self.access))

    def refresh_access_and_add(self, track_uris):
        self.access = send_refresh_token(self.access['refresh_token'])
        if self.access is None:
            raise self.LoginError
        else:
            save_access(json.dumps(self.access))
            self.add_to_playlist(track_uris)

    def add_to_playlist(self, track_uris):
        response = requests.post(f'https://api.spotify.com/v1/playlists/{self.playlist_id}/tracks',
                                 headers={'Authorization': f'Bearer {self.access["access_token"]}'},
                                 params={'uris': track_uris})

        if response.status_code == requests.codes.unauthorized:
            self.refresh_access_and_add(track_uris)
        elif response.status_code == requests.codes.ok:
            log(f'added to playlist {track_uris}')
        else:
            # @todo this prints on successful adds. probably bc the response.status_code == requests.codes.created
            log_error(f'failed to add tracks {track_uris}')
            log(response.text)


def get_track_id(url):
    # @todo error handling when we linked something besides a track
    m = re.search('/track/([a-zA-Z0-9]+)$', url.path)
    return m.group(1)


def parse_urls(string):
    regex = re.compile(r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|
                       (\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))""",
                       re.VERBOSE)
    url = regex.findall(string)
    return [x[0] for x in url]


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


def banner():
    return """begin botting
     _           _   _  __
    | |         | | (_)/ _|
 ___| |__   ___ | |_ _| |_ _   _
/ __| '_ \\ / _ \\| __| |  _| | | |
\\__ \\ |_) | (_) | |_| | | | |_| |
|___/_.__/ \\___/ \\__|_|_|  \\__, |
                            __/ |
                           |___/
    """


log(banner())
check_env_vars()
discord_client = discord.Client()
try:
    bot = Bot()
except Bot.LoginError:
    log_error('failed to login to spotify')
    exit(1)


@discord_client.event
async def on_message(message):
    if os.getenv('TEST'):
        return

    for url in parse_urls(message.content):
        u = urlparse(url)
        if 'spotify' in u.netloc:
            try:
                track_id = get_track_id(u)
            except IndexError:
                log_error(f'failed to get track_id from {u.path}')
            else:
                bot.add_to_playlist(f'spotify:track:{track_id}')

# @todo test Bot.refresh_access_and_add()
# @todo add a request history and on startup check this list against what's in the chat. send requests if needed.
# @todo add a check against the playlist's items and on startup check this list against what's in the chat. send requests if needed.
# @todo add different channels to different playlists (multi-channel -> respective playlist support)


def main():
    log('Starting client')
    discord_client.run(os.getenv('DISCORD_TOKEN'))


main()

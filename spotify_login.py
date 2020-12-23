import os
import json
import requests
from base64 import b64encode


client_id = os.environ["SPOTIFY_CLIENT_ID"]
client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
output_file = 'spotify.json'


def save_access(access):
    with open(output_file, 'w') as f:
        f.write(json.dumps(access))
    os.chmod(output_file, 0o600)


def tell_user_to_authorize():
    redirect_uri = 'http%3A%2F%2Flocalhost%3A5000'
    scope = 'playlist-modify-public'  # space delimited

    print('login required')
    print(f' https://accounts.spotify.com/authorize?'
        f'response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}')
    print('what is the code?')
    return input()


def send_auth_code(code):
    encoded_secrets = b64encode(f'{client_id}:{client_secret}'.encode('utf8')).decode('utf8')
    return requests.post(
        'https://accounts.spotify.com/api/token',
        headers={'Authorization': f'Basic {encoded_secrets}'},
        data={
            'grant_type': 'authorization_code',
            'redirect_uri': 'http://localhost:5000',
            'code': code,
        })


if __name__ == '__main__':
    authorization_code = tell_user_to_authorize()
    response = send_auth_code(authorization_code)

    if response.status_code == requests.codes.ok:
        save_access(json.loads(response.text))
    else:
        print(f'{response.status_code}')
        print(f'{response.text}')

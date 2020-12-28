## Inital Setup
This only needs to be done once.
```sh
$ openssl enc -d -aes-256-cbc -base64 -pbkdf2 -in .env.secrets -out .env
$ virtualenv venv -p /usr/bin/python3
$ source venv/bin/activate
$ pip install -r requirements.txt
```

## Hosting
Currently hosted on an EC2 AWS instance running out of `~/sbotify`.
```sh
$ systemctl start supervisord
```

### Initial Setup
Supervisord runs programs as services. `sbotify.ini` is included to configure supervisord
to run this bot as a service on whatever unix like system you're hosting on. Create a
symbolic link to the system directory and restart supervisord.
```sh
$ ln -s sbotify.ini /etc/supervisord.d/sbotify.ini
$ systemctl restart supervisord
```

## Re-encrypt keys
```sh
$ openssl enc -aes-256-cbc -base64 -pbkdf2 -in .env -out .env.secrets
```

## Spotify API
#### Get user ID
```sh
$ http https://api.spotify.com/v1/me "Authorization: Bearer ${ACCESS_TOKEN}"
```

#### Get playlists
```sh
$ http https://api.spotify.com/v1/me/playlists "Authorization: Bearer ${ACCESS_TOKEN}"
    | jq '.items[] | "\(.id) \(.name)"'
```

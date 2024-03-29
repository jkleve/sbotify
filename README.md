# Sbotify

## Table of Contents
- [Get Started](#get-started)
- [Develop](#develop)
- [Spotify API](#spotify-api)

# Get Started

For steps to set up a VM to run this application see [the provision guide here](./docs/provision-vm.md).

## Develop

```sh
# Don't forget to activate environment.
source venv/bin/activate

# Run dev server. The default port is 5000.
flasek --app src/app.py run
```

Run a test command.

```sh
curl -X POST -H "Content-Type: application/json" '{"msg":"hello, world"}' -Sv 127.0.0.1:5000/sms-text
```

See [the developers guide here](./docs/developers-guide.md).

## Spotify API

Sbotify uses spotify's API to manage playlists. See [the spotify api guide](./docs/spotify-api.md) for more information.


# Deprecated or out-of-date

TODO(jkleve) clean up. I'm not sure if my old set up used nginx.

## Hosting
Currently hosted on an EC2 AWS instance running out of `~/sbotify`.
```sh
$ systemctl start supervisord
```

Supervisord runs programs as services. `sbotify.ini` is included to configure supervisord
to run this bot as a service on whatever unix like system you're hosting on. Create a
symbolic link to the system directory and restart supervisord.
```sh
$ ln -s sbotify.ini /etc/supervisord.d/sbotify.ini
$ systemctl restart supervisord
```

### Serve sbotify logs
Add an inbound rule on the EC2 instance to allow connections on port 80. Also...
```sh
# install nginx
$ ln -s sbotify.conf /etc/nginx/conf.d/sbodify.conf
$ ln -s sbotify.log /usr/share/nginx/html/index.txt
$ systemctl enable nginx
$ systemctl start nginx
```
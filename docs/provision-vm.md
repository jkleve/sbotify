
# How to get a VM set up

## Table of Contents
- [Provision VM](#provision-vm)
- [Decrypt secrets](#decrypt-secrets)
- [Configure python](#configure-python)
- [Configure nginx](#configure-nginx)
- [Next](#next)

## Provision VM

```sh
ssh root@<ip>
ssh-keygen -t rsa -b 4096
# copy to GitHub

mkdir /app
cd /app
git clone <repo>
apt update
apt upgrade
shutdown -r now

apt install supervisord
apt install python3 virtualenv pip
```

## Decrypt secrets

```sh
openssl enc -d -aes-256-cbc -base64 -pbkdf2 -in .env.secrets -out .env
```

If you ever have to re-encrypt the secrets you can use:

```sh
openssl enc -aes-256-cbc -base64 -pbkdf2 -in .env -out .env.secrets
```

## Configure python

```sh
# create a virtual environment
virtualenv venv -p /usr/bin/python3

# activate environment
source venv/bin/activate

# install requirements
pip install -r requirements.txt
```

## Configure nginx 

## Next

See:
- [Developers Guide](./developers-guide.md)
- [Production Guide](./production-guide.md)

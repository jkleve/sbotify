# import discord
import os
import json
import pytz
import re
import requests
from base64 import b64encode
from datetime import datetime, timedelta
from flask import abort, Flask, jsonify, request
from urllib.parse import urlparse

from . import logger
from . import spotify
# from src import logger


__author__ = 'Jesse Kleve'
__version__ = '0.8.0'


app = Flask(__name__)


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
                        logger.info(f'billboard {url.geturl()} to {message.guild.name}:{channel.name}')
                        posted = True
                    if channel.name == 'other':
                        other_channel = channel
                if not posted and other_channel is not None:
                    await other_channel.send(msg)
                    logger.info(f'billboard {url.geturl()} to {message.guild.name}:{other_channel.name}')


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

    def __init__(self, url_handlers: UrlHandlers):
        logger.info(self.banner())
        self._handlers = [url_handlers, ]

    async def handle_message(self, message):
        # logger.trace(f'from {message.author.display_name}: {message.content}')
        for handler in self._handlers:
            await handler.handle(message)

        # client = discord.Client()

        # @client.event
        # async def on_message(message):
        #     if message.author == client.user:
        #         return

        #     if os.getenv('TEST') and message.guild.name != 'test':
        #         return

        #     logger.trace(f'from {message.author.display_name}: {message.content}')
        #     for handler in [url_handlers, ]:
        #         await handler.handle(message)

        # if not os.getenv('NO_START'):
        #     client.run(os.getenv('DISCORD_TOKEN'))


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


bot = Bot(UrlHandlers(spotify.Spotify()))


def handle_sms_msg(msg) -> bool:
    logger.info(f"Recieved {msg}")
    return bot.handle_message(msg)


@app.route("/sms-text", methods=["POST"])
def sms_text():
    msg = request.form.get("msg")
    if handle_sms_msg(msg):
        return jsonify(msg="Created"), 201
    return jsonify(msg="Something went wrong"), 500

if __name__ == '__main__':
    app.run(debug=True)
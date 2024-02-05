import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
# logging.basicConfig(
#     filename='sbotify.log', level=logging.INFO,
#     datefmt='%y-%m-%d %H:%M:%S', format='%(asctime)s | %(levelname)5s | %(message)s')
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('discord').setLevel(logging.CRITICAL)


def info(msg):
    logging.info(msg)


def trace(msg):
    pass


def debug(msg):
    logging.debug(msg)


def error(msg):
    logging.error(msg)

import socket
from time import time
import logging
logging.basicConfig(level=logging.INFO)

DEFAULT_PORT = 1666
DEFAULT_HOST = '255.255.255.255'
DEFAULT_INTERVAL = 1.0 # seconds


class Broadcaster:
    def __init__(self, omxplayer, options = {}):
        # config
        self.player = omxplayer
        self.options = options
        self.interval = options['interval'] if 'interval' in options else DEFAULT_INTERVAL
        # attributes
        self.socket = None
        self.next_broadcast_time = 0

        self.logger = logging.getLogger(__name__)
        if 'verbose' in options and options['verbose']:
            self.logger.setLevel(logging.DEBUG)

    def __del__(self):
        self.destroy()

    def setup(self):
        host = self.options['host'] if 'host' in self.options else DEFAULT_HOST
        port = self.options['port'] if 'port' in self.options else DEFAULT_PORT

        # create socket connections
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        # enable broadcasting
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        try:
            self.socket.connect((host, port))
        except:
            self.logger.error('socket.connect failed; network is unreachable')

    def destroy(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def update(self):
        t = time()

        # time for next broadcast?
        if t >= self.next_broadcast_time:
            # broadcast
            self._broadcast_position()
            # "schedule" next broadcast
            self.next_broadcast_time = t + self.interval

    def _broadcast_position(self):
        p = self.player.position()
        filename = self.player.get_filename()

        if not p and not filename:
            return

        try:
            self.socket.send(("%s%%%s" % (str(p),  filename)).encode('utf-8'))
        except socket.error as err:
            self.logger.error("socket.send failed:\n{0}".format(err))

        self.logger.debug('broadcast position: {0} with filename: {1}'.format(p, filename))

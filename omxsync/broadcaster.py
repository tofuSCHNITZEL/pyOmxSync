import socket
from time import time
from threading import Thread

DEFAULT_PORT = 1666
DEFAULT_HOST = '255.255.255.255'
DEFAULT_INTERVAL = 1.0 # seconds

class Broadcaster:
    def __init__(self, omxplayer, options = {}):
        # config
        self.player = omxplayer
        self.options = options
        self.verbose = options['verbose'] if 'verbose' in options else False
        self.interval = options['interval'] if 'interval' in options else DEFAULT_INTERVAL
        # attributes
        self.socket = None
        self.next_broadcast_time = 0
        self.update_thread = Thread(target=self.update_loop())

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
            self.update_thread.start()
        except:
            print("PositionBroadcaster: network is unreachable")

    def destroy(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def update_loop(self):
        while self.player.playback_status() != "Stopped":
            self.update()

    def update(self):
        t = time()

        # time for next broadcast?
        if t >= self.next_broadcast_time:
            # broadcast
            self._broadcast_position()
            # "schedule" next broadcast
            self.next_broadcast_time = t + self.interval

    def _broadcast_position(self):
        duration = self.player.duration()
        playback_status = self.player.playback_status()
        p = self.player.position()

        if not p and not duration and not playback_status:
            return

        try:
            self.socket.send(("%s%%%s%%%s" % (str(p),  duration, playback_status)).encode('utf-8'))
        except socket.error as err:
            print("PositionBroadcaster: socket.send failed:")
            print(err)

        if self.verbose:
            print('broadcast position: %s of %s' % (str(p), duration))

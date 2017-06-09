import socket
from time import time
from threading import Thread

DEFAULT_PORT = 1666
DEFAULT_HOST = '255.255.255.255'
DEFAULT_INTERVAL = 1.0 # seconds

class Broadcaster:
    def __init__(self, omxplayer, verbose=False, interval=DEFAULT_INTERVAL, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 background=True):
        # config
        self.player = omxplayer
        self.verbose = verbose if type(verbose) is bool else False
        self.interval = interval if type(interval) in (int, float) else DEFAULT_INTERVAL
        self.host = self.test_host(host)
        self.port = port if type(port) is int else DEFAULT_PORT
        self.background = background if type(background) is bool else True
        # attributes
        self.socket = None
        self.next_broadcast_time = 0
        self.update_thread = None
        if self.background is True:
            self.setup()
            self.update_thread = Thread(target=self.update_loop())
            self.update_thread.start()
            self.update_thread.join()
            # self.start_thread()

    def __del__(self):
        self.destroy()

    def test_host(self, host):
        host_test = host.split('.', 3)
        try:
            all(int(item) for item in host_test)
            if len(host_test) == 4:
                return host
        except:
            return DEFAULT_HOST

    def setup(self):
        # create socket connections
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        # enable broadcasting
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        try:
            self.socket.connect((self.host, self.port))
        except:
            print("PositionBroadcaster: network is unreachable")

    def start_thread(self):
        self.update_thread = Thread(target=self.update_loop())
        self.update_thread.start()

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

import socket
import struct
from time import time, sleep
from threading import Thread
from dbus import DBusException

DEFAULT_PORT = 1666
DEFAULT_HOST = '224.0.0.251'
DEFAULT_INTERVAL = 1.0 # seconds

class Broadcaster:
    def __init__(self, omxplayer, verbose=False, interval=DEFAULT_INTERVAL, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 background=True, interface=None):
        # config
        self.player = omxplayer
        self.verbose = verbose if type(verbose) is bool else False
        self.interval = interval if type(interval) in (int, float) else DEFAULT_INTERVAL
        host = self.test_host(host)
        port = port if type(port) is int else DEFAULT_PORT
        self.multicast = (host, port)
        self.background = background if type(background) is bool else True
        self.interface = interface
        # attributes
        self.socket = None
        self.next_broadcast_time = 0
        self.update_thread = None
        self.message = " "
        while self.setup() is False:
            sleep(1)
        if self.background is True:
            self.start_thread()

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
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        ttl = struct.pack('b', 32)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        # enable broadcasting
        if self.interface is not None:
            self.socket.setsockopt(socket.SOL_SOCKET, 25, self.interface)

    def start_thread(self):
        self.update_thread = Thread(target=self.update_loop)
        self.update_thread.start()

    def destroy(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def update_loop(self):
        while True:
            try:
                self.update()
            except DBusException:
                self.socket.close()
                break

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
            self.socket.sendto(("%s%%%s%%%s" % (str(p), duration, playback_status)).encode('utf-8'), self.multicast)
            self.message = 'broadcast position: %.2f/%.2f Playback:%s' % (p, duration, playback_status)
        except socket.error:
            self.message = "Network is unreachable"
        if self.verbose:
            print(self.message)

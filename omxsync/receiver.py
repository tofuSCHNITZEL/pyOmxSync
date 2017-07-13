import socket
from dbus import DBusException
from time import time
import collections
from threading import Thread

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 1666

DEFAULT_BIG_TOLERANCE = 3 # amount of deviation above which a large sync should be performed
DEFAULT_TOLERANCE = .05 # margin that is considered acceptable for slave to be ahead or behind
DEFAULT_GRACE_TIME = 3 # amount of time to wait with re-syncs after a resync

class Receiver:
    def __init__(self, omxplayer, verbose=False, big_tolerance=DEFAULT_BIG_TOLERANCE, tolerance=DEFAULT_TOLERANCE,
                 grace_time=DEFAULT_GRACE_TIME, host=DEFAULT_HOST, port=DEFAULT_PORT, background=True):
        # config
        self.player = omxplayer
        self.verbose = verbose if type(verbose) is bool else False
        self.big_tolerance = big_tolerance if type(big_tolerance) in (int, float) else DEFAULT_BIG_TOLERANCE
        self.tolerance = tolerance if type(tolerance) in (int, float) else DEFAULT_TOLERANCE
        self.grace_time = grace_time if type(grace_time) in (int, float) else DEFAULT_GRACE_TIME
        self.host = self.test_host(host)
        self.port = port if type(port) is int else DEFAULT_PORT
        self.background = background if type(background) is bool else True
        # attributes
        self.socket = None
        self.received_position = None
        self.received_duration = None
        self.received_status = None
        self.paused_until = None
        self.deviation = 0
        self.deviations = collections.deque(maxlen=10)
        self.median_deviation = 0
        self.duration_match = None
        self.rate = 1
        self.update_thread = None
        self.message = " "
        self.net_errors = 0
        self.setup()
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
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        # non-blocking, please
        self.socket.setblocking(0)
        # bind to configured host/port
        self.socket.bind((self.host, self.port))
        if self.verbose:
            print('Connection set up')

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
        # keep receiving data so don't get whole batch of data later
        data = self._receive_data()
        local_pos = self.player.position()
        if local_pos is None: # we'll need our own local position
            return
        local_status = self.player.playback_status()
        if local_status is None:
            return

        # no data? no action.
        if not data:
            return

        # store received data
        self.received_position = float(data[0])
        self.received_duration = float(data[1])
        self.received_status = data[2]

        if local_status != self.received_status:
            self.player.play_pause()

        if self.received_status == 'Paused':
            return

        # calculate current deviation based on newly received master position
        self.deviation = self.received_position - local_pos

        self.message = 'Master: %.2f/%.2f (deviation: %.2f, %s, rate: %s)' % \
                       (self.received_duration, self.received_position, self.deviation, local_status, self.rate)
        if self.verbose:
            print self.message

        # check file; if master is playing a different file, then there is no use in time-syncing
        if self.duration_match is None:
            if abs(self.received_duration - float(self.player.duration())) > 1:
                print('Error: durations of files does not match! Master:%s Slave%s' %
                      (self.received_duration, self.player.duration()))
                return
            else:
                self.duration_match = True

        # calculate median deviation
        self.deviations.append(self.deviation)
        self.median_deviation = self._calculate_median(list(self.deviations))

        if self.verbose:
            print('PositionReceiver.median_deviation: ' + str(self.median_deviation))

        # still at start or end of video, don't sync
        if self.received_position <= self.grace_time:  # or self.player.position() <= self.grace_time:
            return

        if (self.received_duration - local_pos) < self.grace_time:
            if self.rate != 1:
                self._reset_small_sync()
            return

        # not deviated very much, nothing to sync
        if abs(self.median_deviation) <= self.tolerance:
            if self.rate != 1:
                self._reset_small_sync()
            return

        # ok, let's do some syncing
        self.deviations.clear()

        if abs(self.median_deviation) >= self.big_tolerance:
            self._perform_big_sync()
            return

        self._perform_small_sync()

    def _receive_data(self):
        try:
            # read incoming socket data
            pos, duration, playback_status = self.socket.recv(1024).decode('utf-8').split('%', 2)
            self.net_errors = 0
            return (pos, duration, playback_status)
        except Exception as e:
            self.net_errors += 1
            if self.net_errors > 20:
                self.message = "Error: Network is unreachable"
                if self.verbose:
                    print self.message
                    print e

        return None

    def _calculate_median(self, lst):
        quotient, remainder = divmod(len(lst), 2)
        if remainder:
            return sorted(lst)[quotient]
        return float(sum(sorted(lst)[quotient - 1:quotient + 1]) / 2.0)

    def _perform_small_sync(self):
        if self.deviation < 0 and self.rate > 0:
            self.player.action(1)
            self.rate -= 1
        elif self.deviation > 0 and self.rate < 2:
            self.player.action(2)
            self.rate += 1

    def _reset_small_sync(self):
            if self.rate == 2:
                self.player.action(1)
            elif self.rate == 0:
                self.player.action(2)
            self.rate = 1

    def _perform_big_sync(self):
        # jump to master position
        self.player.set_position(self.received_position)

        if self.verbose:
            print("jumped to position %.2f" % self.received_position)

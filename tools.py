import collections.abc
import shlex
import signal
import subprocess
from datetime import datetime


def sys_time_offset(frame_ts, car_ts):
    offset = round(car_ts - frame_ts, 3)
    return offset


def fix_sys_time(offset):
    now = datetime.now().timestamp()
    now += offset
    time_string = datetime.fromtimestamp(now).isoformat()
    subprocess.call(shlex.split("date -s '%s'" % time_string))


def deep_update(source, overrides):
    """
    Update a nested dictionary or similar mapping.
    Modify ``source`` in place.
    """
    for key, value in overrides.items():
        if isinstance(value, collections.abc.Mapping) and value:
            source[key] = deep_update(source.get(key, {}), value)
        else:
            source[key] = value
    return source


# source code
# shamelessly copied from
# https://stackoverflow.com/a/31464349/2591014
class GracefulKiller:
    kill_now = False
    signals = {signal.SIGTERM: "SIGTERM"}

    def __init__(self):
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True

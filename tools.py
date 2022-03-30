import collections.abc
import signal


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

    def exit_gracefully(self):
        self.kill_now = True

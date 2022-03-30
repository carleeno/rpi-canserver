import collections.abc
from typing import Tuple

from can import ASCWriter, Message
from can.util import channel2int

"""
Message has no __dict__ attr, meaning we need to json serialize it ourselves.
Attrs:
    timestamp: float
    arbitration_id: int
    is_extended_id: bool
    is_remote_frame: bool
    is_error_frame: bool
    channel: Optional[typechecking.Channel]
    dlc: Optional[int]
    data: Optional[typechecking.CanData]
    is_fd: bool
    is_rx: bool
    bitrate_switch: bool
    error_state_indicator: bool

"""


def serialize_msg(msg: Message) -> Tuple[float, str]:
    serialized = ASCWriter.FORMAT_MESSAGE.format(
        channel=channel2int(msg.channel),
        id=f"{msg.arbitration_id:X}",
        dir="Rx",
        dtype=f"d {msg.dlc:x}",
        data=" ".join([f"{byte:02X}" for byte in msg.data]),
    )
    return (msg.timestamp, serialized)


def deserialize_msg(msg: Tuple[float, str]) -> Message:
    timestamp = msg[0]
    serialized = msg[1]
    channel, rest_of_message = serialized.split(None, 1)
    if channel.isdigit():
        channel = int(channel) - 1
    msg_kwargs = {"timestamp": timestamp, "channel": channel}
    msg = _process_classic_can_frame(rest_of_message, msg_kwargs)
    return msg


def _extract_can_id(str_can_id: str, msg_kwargs) -> None:
    if str_can_id[-1:].lower() == "x":
        msg_kwargs["is_extended_id"] = True
        can_id = int(str_can_id[0:-1], 16)
    else:
        msg_kwargs["is_extended_id"] = False
        can_id = int(str_can_id, 16)
    msg_kwargs["arbitration_id"] = can_id


def _process_data_string(data_str: str, data_length: int, msg_kwargs) -> None:
    frame = bytearray()
    data = data_str.split()
    for byte in data[:data_length]:
        frame.append(int(byte, 16))
    msg_kwargs["data"] = frame


def _process_classic_can_frame(line: str, msg_kwargs) -> Message:
    abr_id_str, direction, rest_of_message = line.split(None, 2)
    msg_kwargs["is_rx"] = direction == "Rx"
    _extract_can_id(abr_id_str, msg_kwargs)

    try:
        # There is data after DLC
        _, dlc_str, data = rest_of_message.split(None, 2)
    except ValueError:
        # No data after DLC
        _, dlc_str = rest_of_message.split(None, 1)
        data = ""

    dlc = int(dlc_str, 16)
    msg_kwargs["dlc"] = dlc
    _process_data_string(data, dlc, msg_kwargs)

    return Message(**msg_kwargs)


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

import signal


class GracefulKiller:
    kill_now = False
    signals = {signal.SIGTERM: "SIGTERM"}

    def __init__(self):
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True

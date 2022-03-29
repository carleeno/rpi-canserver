import collections.abc

from can import Message

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

This also shortens the attr keys to make messages smaller
"""
_key_map = {
    "ts": "timestamp",
    "id": "arbitration_id",
    "ext": "is_extended_id",
    "rmt": "is_remote_frame",
    "err": "is_error_frame",
    "ch": "channel",
    "dlc": "dlc",
    "dt": "data",
    "fd": "is_fd",
    "rx": "is_rx",
    "btr": "bitrate_switch",
    "esi": "error_state_indicator",
}


def msg_to_json(msg: Message) -> dict:
    dict_message = {}
    for key, attr_name in _key_map.items():
        if key == "dt" and (
            isinstance(msg.data, bytearray) or isinstance(msg.data, bytes)
        ):
            dict_message[key] = int.from_bytes(msg.data, "little")
        else:
            dict_message[key] = getattr(msg, attr_name)
    return dict_message


def json_to_msg(json_msg: dict) -> Message:
    msg = Message()
    for key, value in json_msg.items():
        if key == "dt" and isinstance(value, int):
            value = value.to_bytes(json_msg["dlc"], "little")
        setattr(msg, _key_map[key], value)
    return msg


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

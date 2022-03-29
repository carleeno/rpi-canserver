import logging

import socketio

from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger("canserver.socketio")

sio = socketio.Server()
app = socketio.WSGIApp(
    sio,
    static_files={
        "/": "./public/",
    },
)


@sio.event
def connect(sid, environ):
    username = environ.get("HTTP_X_USERNAME")
    if not username:
        username = "(no username)"

    with sio.session(sid) as s:
        s["username"] = username

    logger.info(f"{username} connected")


@sio.event
def disconnect(sid):
    with sio.session(sid) as s:
        username = s["username"]

    logger.info(f"{username} disconnected")


@sio.event
def broadcast_can_frame_batch(sid, data):
    sio.emit("can_frame_batch", data, to="raw_can")


@sio.event
def broadcast_message(sid, message):
    sio.send(message)


@sio.event
def broadcast_stats(sid, data):
    sio.emit("stats", data)


@sio.event
def broadcast_start_logging(sid):
    sio.emit("start_logging")
    sio.send("Logging start request sent")


@sio.event
def broadcast_stop_logging(sid):
    sio.emit("stop_logging")
    sio.send("Logging stop request sent")


@sio.event
def enter_room(sid, room):
    sio.enter_room(sid, room)
    sio.send(f"You're now in '{room}'", to=sid)


@sio.event
def leave_room(sid, room):
    sio.leave_room(sid, room)
    sio.send(f"You're no longer in '{room}'", to=sid)

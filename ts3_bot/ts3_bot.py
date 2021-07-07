import os
from typing import Dict, List, Optional

import preflyt
from dotenv import load_dotenv
from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from matrix_bot_api.mregex_handler import MRegexHandler
from matrix_client.room import Room
from paramiko import client
from ts3API import Events
from ts3API.TS3Connection import TS3Connection, TS3QueryException

CONFIG_FILE = "bot_cfg.json"
TS3_CONN: Optional[TS3Connection] = None
MATRIX_ROOMS: List[Room] = []
CONNECTED_CLIENTS: Dict[int, str] = {}


def on_event(sender, **kw):
    global CONNECTED_CLIENTS

    event = kw["event"]
    try:
        client_info = TS3_CONN.clientinfo(event.client_id)
    except TS3QueryException:
        pass
    channels = TS3_CONN.channellist()
    target_channel: Optional[Dict] = None
    text: Optional[str] = None

    for channel in channels:
        if channel["cid"] == str(event.target_channel_id):
            target_channel = channel

    if isinstance(event, Events.ClientLeftEvent):
        text = f"{CONNECTED_CLIENTS.get(event.client_id, 'Somebody')} disconnected"
        CONNECTED_CLIENTS.pop(event.client_id)
    elif client_info["client_type"] == "0":
        if isinstance(event, Events.ClientMovedSelfEvent) or isinstance(
            event, Events.ClientMovedSelfEvent
        ):
            text = f"{client_info['client_nickname']} moved to {target_channel['channel_name']}"
        elif isinstance(event, Events.ClientEnteredEvent):
            text = f"{client_info['client_nickname']} connected"
            CONNECTED_CLIENTS[event.client_id] = client_info["client_nickname"]
        elif isinstance(event, Events.ClientKickedEvent):
            text = f"{client_info['client_nickname']}, get out!"

    if text is not None:
        for room in MATRIX_ROOMS:
            room.send_text(text)


def main():
    load_dotenv()
    global URI
    global TS3_CONN

    ok, _ = preflyt.check(
        [
            {"checker": "env", "name": "MATRIX_USERNAME"},
            {"checker": "env", "name": "MATRIX_PASS"},
            {"checker": "env", "name": "MATRIX_SERVER"},
            {"checker": "env", "name": "TS_HOST"},
            {"checker": "env", "name": "TS_USERNAME"},
            {"checker": "env", "name": "TS_PASSWORD"},
            {"checker": "env", "name": "EVENT_ROOMS"},
        ]
    )

    if not ok:
        print("Not all required config options are specified")
        return

    user, password, server = (
        os.getenv("MATRIX_USERNAME"),
        os.getenv("MATRIX_PASS"),
        os.getenv("MATRIX_SERVER"),
    )
    ts_user, ts_password, ts_server = (
        os.getenv("TS_USERNAME"),
        os.getenv("TS_PASSWORD"),
        os.getenv("TS_HOST"),
    )
    event_rooms = os.getenv("EVENT_ROOMS").split(",")

    matrix_bot = setup_matrix_bot(user, password, server)

    ts3conn = TS3Connection(ts_server)
    ts3conn.login(ts_user, ts_password)
    ts3conn.use(1)

    TS3_CONN = ts3conn

    for send_room in event_rooms:
        MATRIX_ROOMS.append(matrix_bot.client.rooms.get(send_room))

    ts3conn.register_for_server_events(on_event)
    ts3conn.register_for_channel_events(0, on_event)
    ts3conn.register_for_unknown_events(on_event)
    ts3conn.start_keepalive_loop()


def setup_matrix_bot(username, password, server):
    bot = MatrixBotAPI(username, password, server)

    ts_online = MRegexHandler("^!ts", show_online_clients)
    bot.add_handler(ts_online)

    bot.start_polling()

    return bot


def show_online_clients(room: Room, _):
    clients = TS3_CONN.clientlist()
    actual_clients = []
    for client in clients:
        if client["client_nickname"] is not None and client["client_type"] == "0":
            actual_clients.append(client["client_nickname"])

    room.send_text("Users online: " + ", ".join(actual_clients))


if __name__ == "__main__":
    main()

import os
import threading
from typing import List

from dotenv import load_dotenv
from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from matrix_bot_api.mregex_handler import MRegexHandler
from matrix_client.room import Room

import preflyt
import ts3

CONFIG_FILE = "bot_cfg.json"
URI = None


def main():
    load_dotenv()
    global URI

    ok, _ = preflyt.check(
        [
            {"checker": "env", "name": "MATRIX_USERNAME"},
            {"checker": "env", "name": "MATRIX_PASS"},
            {"checker": "env", "name": "MATRIX_SERVER"},
            {"checker": "env", "name": "TS_URI"},
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
    URI = os.getenv("TS_URI")
    event_rooms = os.getenv("EVENT_ROOMS").split(",")

    matrix_bot = setup_matrix_bot(user, password, server)
    ts3_thread = threading.Thread(target=check_join_and_leave, args=(matrix_bot, event_rooms))

    ts3_thread.start()
    ts3_thread.join()


def setup_matrix_bot(username, password, server):
    bot = MatrixBotAPI(username, password, server)

    ts_online = MRegexHandler("^!ts", show_online_clients)
    bot.add_handler(ts_online)

    bot.start_polling()

    return bot


def show_online_clients(room: Room, _):
    with ts3.query.TS3ServerConnection(URI) as ts3conn:
        ts3conn.exec_("use", sid=1)

        clients = []

        for client in ts3conn.exec_("clientlist"):
            if client.get("client_nickname") is not None and client.get("client_type") == "0":
                print(client)
                clients.append(client.get("client_nickname"))

        room.send_text("Users online: " + ", ".join(clients))


def check_join_and_leave(bot: MatrixBotAPI, send_rooms: List[str]):
    """
    :param bot: is a bot
    """

    # maps clid to client_nickname
    online_clients = {}

    room_objs: List[Room] = []

    for send_room in send_rooms:
        room_objs.append(bot.client.rooms.get(send_room))

    with ts3.query.TS3ServerConnection(URI) as ts3conn:
        ts3conn.exec_("use", sid=1)

        # Register for events
        ts3conn.exec_("servernotifyregister", event="server")

        while True:
            ts3conn.send_keepalive()

            try:
                event = ts3conn.wait_for_event(timeout=60)
            except (ts3.query.TS3TimeoutError, ts3.query.TS3QueryError):
                pass
            else:
                room_text = ""
                # Greet new clients.
                if event[0]["reasonid"] == "0" and event[0]["client_type"] == "0":
                    room_text = f"{event[0]['client_nickname']} connected"
                    online_clients[event[0]["clid"]] = event[0]["client_nickname"]
                elif event[0]["reasonid"] == "8":
                    if event[0]["clid"] in online_clients:
                        room_text = f"{online_clients.get(event[0]['clid'])} disconnected"
                        online_clients.pop(event[0]["clid"])
                    else:
                        room_text = "Somebody disconnected"
                elif event[0]["reasonid"] == "4":
                    if event[0]["clid"] in online_clients:
                        room_text = f"{online_clients.get(event[0]['clid'])} was kicked"
                        online_clients.pop(event[0]["clid"])
                    else:
                        room_text = "Somebody was kicked"
                if room_text != "":
                    for room in room_objs:
                        room.send_text(room_text)


if __name__ == "__main__":
    main()

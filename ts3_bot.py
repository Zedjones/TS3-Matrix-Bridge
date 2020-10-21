import json
import threading

from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from matrix_bot_api.mregex_handler import MRegexHandler
import ts3

CONFIG_FILE = "bot_cfg.json"
URI = None


def main():
    global URI

    config = json.loads(open("bot_cfg.json", "r").read())
    user, password, server = (
        config["matrix_username"],
        config["matrix_pass"],
        config["matrix_server"],
    )
    URI = config["ts_uri"]
    event_rooms = config["event_rooms"]

    matrix_bot = setup_matrix_bot(user, password, server)
    ts3_thread = threading.Thread(
        target=check_join_and_leave, args=(matrix_bot, event_rooms)
    )

    ts3_thread.start()
    ts3_thread.join()


def setup_matrix_bot(username, password, server):
    bot = MatrixBotAPI(username, password, server)

    ts_online = MRegexHandler("^!ts", show_online_clients)
    bot.add_handler(ts_online)

    bot.start_polling()

    return bot


def show_online_clients(room, _):
    with ts3.query.TS3ServerConnection(URI) as ts3conn:
        ts3conn.exec_("use", sid=1)

        clients = []

        for client in ts3conn.exec_("clientlist"):
            if (
                client.get("client_nickname") is not None
                and client.get("client_type") == "0"
            ):
                print(client)
                clients.append(client.get("client_nickname"))

        room.send_text("Users online: " + ", ".join(clients))


def check_join_and_leave(bot, send_rooms):
    """
    :param bot: is a bot
    :type bot: matrix_bot_api.matrix_bot_api.MatrixBotAPI
    """

    # maps clid to client_nickname
    online_clients = {}

    room_objs = []

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
                # Greet new clients.
                if event[0]["reasonid"] == "0":
                    if event[0]["client_type"] == "0":
                        for room in room_objs:
                            room.send_text(
                                "{} connected".format(event[0]["client_nickname"])
                            )
                        online_clients[event[0]["clid"]] = event[0]["client_nickname"]
                elif event[0]["reasonid"] == "8":
                    for room in room_objs:
                        if event[0]["clid"] in online_clients:
                            room.send_text(
                                "{} disconnected".format(
                                    online_clients.get(event[0]["clid"])
                                )
                            )
                            online_clients.pop(event[0]["clid"])
                        else:
                            room.send_text("Somebody disconnected")
                elif event[0]["reasonid"] == "4" or event[0]["reasonid"] == "4":
                    for room in room_objs:
                        if event[0]["clid"] in online_clients:
                            room.send_text(
                                "{} was kicked".format(
                                    online_clients.get(event[0]["clid"])
                                )
                            )
                            online_clients.pop(event[0]["clid"])
                        else:
                            room.send_text("Somebody was kicked")


if __name__ == "__main__":
    main()

import asyncio
import os
from typing import Callable, Dict, List, Optional

import preflyt
import simplematrixbotlib as botlib
from dotenv import load_dotenv
from nio.rooms import MatrixRoom
from ts3API import Events
from ts3API.TS3Connection import TS3Connection


def create_event_handler(
    bot: botlib.Bot, event_rooms: List[str], ts3_conn: TS3Connection
) -> Callable[[str], None]:
    def on_event(_, **kw):

        matrix_rooms: List[MatrixRoom] = []

        for send_room in event_rooms:
            matrix_rooms.append(bot.api.async_client.rooms[send_room])

        event = kw["event"]
        channels = ts3_conn.channellist()
        target_channel: Optional[Dict] = None
        text: Optional[str] = None

        connected_clients: Dict[int, str] = {}

        for channel in channels:
            if channel["cid"] == str(event.target_channel_id):
                target_channel = channel

        if isinstance(event, Events.ClientLeftEvent):
            text = f"{connected_clients.get(event.client_id, 'Somebody')} disconnected"
            connected_clients.pop(event.client_id, None)
        else:
            client_info = ts3_conn.clientinfo(event.client_id)
            if client_info["client_type"] == "0":
                if isinstance(event, Events.ClientMovedSelfEvent) or isinstance(
                    event, Events.ClientMovedEvent
                ):
                    channel_name = (
                        "a different channel"
                        if target_channel is None
                        else target_channel["channel_name"]
                    )
                    text = f"{client_info['client_nickname']} moved to {channel_name}"
                elif isinstance(event, Events.ClientEnteredEvent):
                    text = f"{client_info['client_nickname']} connected"
                    connected_clients[event.client_id] = client_info["client_nickname"]
                elif isinstance(event, Events.ClientKickedEvent):
                    text = f"{client_info['client_nickname']}, get out!"

        loop = bot.api.async_client.client_session.loop
        asyncio.set_event_loop(loop)
        if text is not None:
            for room in matrix_rooms:
                task = loop.create_task(bot.api.send_text_message(room.room_id, text))
                asyncio.ensure_future(task, loop=loop)

    return on_event


def main():
    load_dotenv()

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

    creds = botlib.Creds(server, user, password)
    bot = botlib.Bot(creds)

    ts3conn = TS3Connection(ts_server)
    ts3conn.login(ts_user, ts_password)
    ts3conn.use(1)

    new_online_clients = show_online_clients_wrapper(bot, ts3conn)
    bot.add_message_listener(new_online_clients)
    poke_client = poke_client_wrapper(bot, ts3conn)
    bot.add_message_listener(poke_client)

    event_handler = create_event_handler(bot, event_rooms, ts3conn)

    ts3conn.register_for_server_events(event_handler, False)
    ts3conn.register_for_channel_events(0, event_handler, False)
    ts3conn.register_for_unknown_events(event_handler, False)
    ts3conn.start_keepalive_loop()

    bot.run()


def show_online_clients_wrapper(bot: botlib.Bot, ts3_conn: TS3Connection):
    async def show_online_clients(room: MatrixRoom, message: str):
        match = botlib.MessageMatch(room, message, bot)
        if match.not_from_this_bot() and match.prefix("!") and match.command("ts"):
            clients = ts3_conn.clientlist()
            actual_clients = []
            for client in clients:
                if (
                    client["client_nickname"] is not None
                    and client["client_type"] == "0"
                ):
                    actual_clients.append(client["client_nickname"])
            await bot.api.send_text_message(
                room.room_id, f"Users online: {', '.join(actual_clients)}"
            )

    return show_online_clients


def poke_client_wrapper(bot: botlib.Bot, ts3_conn: TS3Connection):
    async def poke_client(room: MatrixRoom, message: str):
        match = botlib.MessageMatch(room, message, bot)
        if match.not_from_this_bot() and match.prefix("!") and match.command("poke"):
            try:
                _, username, message = match.args.split('"', 2)
                user = None
                for client in ts3_conn.clientlist():
                    if client["client_nickname"].lower() == username.lower():
                        user = client
                if user is None:
                    await bot.api.send_text_message(
                        room.room_id, f"User {username} is not online!"
                    )
                    return
                ts3_conn.clientpoke(user["clid"], message[1::])
            except ValueError:
                await bot.api.send_text_message(
                    room.room_id, "Command was improperly formatted!"
                )

    return poke_client


if __name__ == "__main__":
    main()

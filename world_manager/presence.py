"""Expiring snapshots shared by Houdini worlds and the moderator panel."""
import asyncio
import json
import time
from datetime import datetime

INTERVAL = 5
TTL = 20
SERVERS = {3100: "blizzard", 3101: "glaciar", 3102: "avalanche", 3103: "yeti"}


def key(server_id):
    return "wand.presence." + str(server_id)


def snapshot(server):
    players = []
    for player in list(server.penguins_by_id.values()):
        if not player.joined_world:
            continue
        room = player.room
        kind = "room"
        owner = None
        if room is not None:
            if getattr(room, "backyard", False):
                kind, owner = "backyard", player.id
            elif getattr(room, "igloo", False):
                kind, owner = "igloo", room.penguin_id
            elif getattr(room, "game", False):
                kind = "game"
        players.append({"id": player.id, "username": player.username, "nickname": player.nickname,
                        "client": "Legacy" if player.is_legacy_client else "Vanilla",
                        "room_id": room.id if room is not None else None,
                        "room_name": room.name if room is not None else "Changing rooms",
                        "room_kind": kind, "owner_id": owner,
                        "seconds_online": max(0, int((datetime.now() - player.login_timestamp).total_seconds()))
                        if player.login_timestamp else 0})
    return {"server_id": server.config.id, "server_name": server.config.name,
            "updated_at": time.time(), "players": sorted(players, key=lambda p: p["id"])}


async def publish(server):
    """Failures in monitoring must never stop a running world."""
    while True:
        if server.redis is not None and server.rooms is not None:
            try:
                await asyncio.wait_for(server.redis.set(key(server.config.id),
                    json.dumps(snapshot(server)), ex=TTL), timeout=2)
            except Exception:
                server.logger.warning("No se pudo actualizar la presencia del manager", exc_info=True)
        await asyncio.sleep(INTERVAL)


def install(houdini_class):
    original = houdini_class.start

    async def start(server):
        if server.config.type != "world":
            return await original(server)
        task = asyncio.create_task(publish(server))
        try:
            return await original(server)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            # Leave the last snapshot to expire. Deleting here could remove a
            # replacement process's snapshot if an old process stops late.
    houdini_class.start = start


async def read_presence(redis):
    values = await redis.mget([key(server_id) for server_id in SERVERS])
    servers, players = [], []
    for (server_id, name), raw in zip(SERVERS.items(), values):
        data = None
        try:
            candidate = json.loads(raw) if raw else None
            if (isinstance(candidate, dict) and candidate.get("server_id") == server_id
                    and isinstance(candidate.get("players"), list)
                    and isinstance(candidate.get("updated_at"), (float, int))):
                data = candidate
        except (ValueError, TypeError, UnicodeError):
            pass
        rows = data["players"] if data else []
        servers.append({"id": server_id, "name": name, "available": data is not None,
                        "count": len(rows) if data else None,
                        "updated_at": data["updated_at"] if data else None})
        for row in rows:
            players.append({**row, "server_id": server_id, "server_name": name})
    return {"servers": servers, "players": players, "updated_at": time.time(),
            "interval": INTERVAL, "ttl": TTL}

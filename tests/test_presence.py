import asyncio
import json
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from world_manager.presence import install, key, publish, read_presence, snapshot, TTL


def server():
    room = types.SimpleNamespace(id=100, name="Town", igloo=False, backyard=False, game=False)
    player = types.SimpleNamespace(id=7, username="penguin", nickname="Penguin", joined_world=True,
        room=room, is_legacy_client=False, login_timestamp=datetime.now() - timedelta(minutes=3))
    return types.SimpleNamespace(config=types.SimpleNamespace(id=3100, name="blizzard", type="world"),
        penguins_by_id={7: player}, redis=types.SimpleNamespace(set=AsyncMock()), rooms={},
        logger=types.SimpleNamespace(warning=lambda *a, **k: None))


class SnapshotTests(unittest.TestCase):
    def test_world_snapshot_has_player_server_room_and_client_without_credentials(self):
        source = server()
        data = snapshot(source)
        self.assertEqual(data["server_id"], 3100)
        player = data["players"][0]
        self.assertEqual((player["id"], player["room_id"], player["room_name"]), (7, 100, "Town"))
        self.assertEqual(player["client"], "Vanilla")
        self.assertGreaterEqual(player["seconds_online"], 180)
        self.assertNotIn("password", json.dumps(data))
        source.penguins_by_id[7].is_legacy_client = True
        self.assertEqual(snapshot(source)["players"][0]["client"], "Legacy")

    def test_moves_disconnects_igloos_backyards_and_games_are_reflected(self):
        source = server()
        player = source.penguins_by_id[7]
        player.room = types.SimpleNamespace(id=29, name="Igloo", igloo=True, backyard=False, penguin_id=40)
        self.assertEqual(snapshot(source)["players"][0]["owner_id"], 40)
        player.room = types.SimpleNamespace(id=1000, name="Backyard", backyard=True)
        self.assertEqual(snapshot(source)["players"][0]["room_kind"], "backyard")
        player.room = types.SimpleNamespace(id=916, name="Aqua", game=True)
        self.assertEqual(snapshot(source)["players"][0]["room_kind"], "game")
        player.room = None
        self.assertEqual(snapshot(source)["players"][0]["room_name"], "Changing rooms")
        source.penguins_by_id.clear()
        self.assertEqual(snapshot(source)["players"], [])


class PresenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_servers_are_unavailable_instead_of_zero_online(self):
        source = server()
        redis = types.SimpleNamespace(mget=AsyncMock(return_value=[json.dumps(snapshot(source)), None, b"corrupt", None]))
        result = await read_presence(redis)
        self.assertEqual(result["servers"][0]["count"], 1)
        self.assertTrue(result["servers"][0]["available"])
        self.assertIsNone(result["servers"][1]["count"])
        self.assertFalse(result["servers"][1]["available"])
        self.assertFalse(result["servers"][2]["available"])
        self.assertEqual(result["players"][0]["server_name"], "blizzard")

    async def test_empty_live_server_is_distinct_from_expired_server(self):
        source = server(); source.penguins_by_id.clear()
        redis = types.SimpleNamespace(mget=AsyncMock(return_value=[json.dumps(snapshot(source)), None, None, None]))
        result = await read_presence(redis)
        self.assertEqual(result["servers"][0]["count"], 0)
        self.assertTrue(result["servers"][0]["available"])

    async def test_publisher_uses_ttl_and_redis_failure_does_not_stop_loop(self):
        source = server()
        source.redis.set.side_effect = [RuntimeError("offline"), None]
        calls = 0
        async def sleep(_):
            nonlocal calls
            calls += 1
            if calls == 2: raise asyncio.CancelledError()
        with patch("world_manager.presence.asyncio.sleep", sleep):
            with self.assertRaises(asyncio.CancelledError):
                await publish(source)
        self.assertEqual(source.redis.set.await_count, 2)
        args, kwargs = source.redis.set.call_args
        self.assertEqual(args[0], key(3100))
        self.assertEqual(kwargs, {"ex": TTL})

    async def test_start_wrapper_cancels_publisher_when_world_stops(self):
        source = server()
        class Houdini:
            async def start(self):
                await asyncio.sleep(0)
                return "done"
        install(Houdini)
        self.assertEqual(await Houdini.start(source), "done")
        # The monitor is cancelled and awaited, leaving no background publisher.
        self.assertFalse(any("publish" in repr(task.get_coro()) for task in asyncio.all_tasks()
                             if task is not asyncio.current_task()))

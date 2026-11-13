"""Runtime configuration, asset isolation, transactions and recovery."""
import json
import io
import struct
import sys
import tempfile
import unittest
import zlib
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from world_manager.store import WorldStore, validate_swf


def swf(payload=b"\x08\x00\x00\x0c\x01\x00\x00\x00"):
    return b"FWS\x09" + struct.pack("<I", len(payload) + 8) + payload


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.media, self.state = root / "media", root / "state"
        rooms = {"100": {"room_id": 100, "room_key": "town", "name": "Town", "path": "town.swf", "music_id": 1},
                 "300": {"room_id": 300, "room_key": "plaza", "name": "Plaza", "path": "plaza.swf", "music_id": 2}}
        for language in ("en", "es"):
            config = self.media / "play" / language / "web_service/game_configs"
            config.mkdir(parents=True)
            config.joinpath("rooms.json").write_text(json.dumps(rooms))
        base = self.media / "media/play/v2/content/global"
        (base / "rooms").mkdir(parents=True)
        (base / "music").mkdir()
        for name in ("town.swf", "plaza.swf", "room_classes.swf"):
            (base / "rooms" / name).write_bytes(swf())
        for name in ("1.swf", "2.swf", "9.swf"):
            (base / "music" / name).write_bytes(swf())
        self.store = WorldStore(self.media, self.state)

    def upload(self, room="100", event="Evento", body=None, music=9):
        return self.store.upload(room, body or swf(b"variant"), "Decoración", event, music)

    def test_runtime_selection_and_asset_keep_original_base_and_survive_restart(self):
        original = self.store.baseline()
        digest = self.upload()
        selection = self.store.selection("100", "upload/" + digest + ".swf", 9)
        self.store.change("mod", 0, "save", room="100", selection=selection)
        restarted = WorldStore(self.media, self.state)
        room = restarted.rooms("es")["100"]
        path = urlsplit(room["path"])
        self.assertEqual(path.path, "town.swf")
        token = parse_qs(path.query)["wand_asset"][0]
        self.assertEqual(restarted.room_file(path.path, token).read_bytes(), swf(b"variant"))
        self.assertEqual(room["music_id"], 9)
        self.assertEqual(restarted.rooms()["300"], original["300"])
        self.assertEqual(restarted.baseline(), original)

    def test_restore_returns_exact_original_configuration(self):
        selection = self.store.selection("100", "original", 0)
        self.store.change("mod", 0, "save", room="100", selection=selection)
        self.store.change("mod", 1, "restore", room="100")
        self.assertEqual(self.store.rooms(), self.store.baseline())
        self.assertEqual(len(self.store.history()), 2)

    def test_event_is_atomic_replaces_previous_and_can_restore_all(self):
        self.upload("100")
        self.upload("300", body=swf(b"plaza"), music=2)
        self.store.change("mod", 0, "event", event="Evento")
        self.assertEqual(set(self.store.snapshot()[1]), {"100", "300"})
        self.assertEqual(self.store.rooms()["100"]["music_id"], 9)
        self.store.change("mod", 1, "restore_all")
        self.assertEqual(self.store.rooms(), self.store.baseline())

    def test_duplicate_room_or_missing_resource_cannot_partially_activate_event(self):
        first = self.upload()
        self.upload(body=swf(b"different"))
        with self.assertRaises(ValueError):
            self.store.change("mod", 0, "event", event="Evento")
        self.assertEqual(self.store.snapshot(), (0, {}))
        self.upload(event="Otro")  # Move first asset out of duplicated group.
        (self.state / "assets" / (first + ".swf")).unlink()
        with self.assertRaises(ValueError):
            self.store.change("mod", 0, "event", event="Otro")
        self.assertEqual(self.store.snapshot(), (0, {}))
        self.assertEqual(self.store.history(), [])

    def test_stale_admin_cannot_overwrite_a_concurrent_change(self):
        selection = self.store.selection("100", "original", 1)
        def save():
            try:
                return self.store.change("mod", 0, "save", room="100", selection=selection)
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: save(), range(2)))
        self.assertEqual(results.count(1), 1)
        self.assertEqual(results.count(None), 1)

    def test_asset_is_bound_to_its_room_and_paths_are_not_user_controlled(self):
        digest = self.upload()
        with self.assertRaises(ValueError):
            self.store.selection("300", "upload/" + digest + ".swf", 1)
        for filename in ("../world.sqlite3", "..\\world.sqlite3", "/etc/passwd", "town.swf/../secret"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                self.store.room_file(filename)
        with self.assertRaises(ValueError):
            self.store.room_file("plaza.swf", digest)
        self.assertTrue(self.store.room_file("room_classes.swf").is_file())

    def test_missing_music_unknown_room_and_remote_urls_are_rejected(self):
        for room, asset, music in (("99999", "original", 1), ("100", "original", 888),
                                   ("100", "https://evil.test/file.swf", 1), ("100", "original", "nan")):
            with self.subTest(room=room, asset=asset, music=music), self.assertRaises(ValueError):
                self.store.selection(room, asset, music)

    def test_swf_validation_rejects_invalid_truncated_and_compression_bombs(self):
        validate_swf(swf())
        body = swf()
        validate_swf(b"CWS" + body[3:8] + zlib.compress(body[8:]))
        for body in (b"not a swf", swf()[:-1], b"CWS\x09" + struct.pack("<I", 9) + zlib.compress(b"a" * 100),
                     b"CWS\x09" + struct.pack("<I", 0xffffffff) + zlib.compress(b"a")):
            with self.subTest(body=body[:8]), self.assertRaises(ValueError):
                validate_swf(body)

    def test_invalid_language_is_not_a_filesystem_path(self):
        with self.assertRaises(ValueError):
            self.store.rooms("../en")

    def test_flash_binary_bundle_changes_rooms_and_preserves_all_other_members(self):
        original = self.store.baseline()
        original["100"]["music_id"] = 2  # The ZIP can differ from standalone JSON.
        path = self.media / "media/play/en/web_service/game_configs.bin"
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("rooms.json", json.dumps(original))
            archive.writestr("general.json", b'{"party_options":{"enabled":true}}')
            archive.writestr("other.bin", bytes(range(256)))
        original_bytes = path.read_bytes()
        self.assertEqual(self.store.baseline()["100"]["music_id"], 2)
        self.assertEqual(self.store.rooms()["100"]["music_id"], 1)
        self.assertEqual(self.store.bundle(), original_bytes)
        digest = self.upload()
        selection = self.store.selection("100", "upload/" + digest + ".swf", 9)
        self.store.change("mod", 0, "save", room="100", selection=selection)
        with zipfile.ZipFile(io.BytesIO(self.store.bundle())) as changed, zipfile.ZipFile(path) as source:
            rooms = json.loads(changed.read("rooms.json"))
            self.assertEqual(rooms["100"]["music_id"], 9)
            self.assertIn(digest, rooms["100"]["path"])
            self.assertEqual(rooms["300"], original["300"])
            self.assertEqual(changed.namelist(), source.namelist())
            for name in ("general.json", "other.bin"):
                self.assertEqual(changed.read(name), source.read(name))
        self.store.change("mod", 1, "restore_all")
        self.assertEqual(self.store.bundle(), original_bytes)


if __name__ == "__main__":
    unittest.main()

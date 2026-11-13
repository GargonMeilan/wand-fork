import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from world_manager.store import WorldStore, validate_swf
import test_world_manager as fixtures


class InstalledCatalogueTests(unittest.TestCase):
    def test_installed_resources_are_real_complete_files_with_verified_hashes(self):
        root = Path(__file__).resolve().parent.parent / "world_manager/catalog"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["events"]), 16)
        town = [e for e in manifest["events"] if any(r["room"] == "100" for r in e["rooms"])]
        self.assertGreaterEqual(len(town), 13)
        checked = set()
        for event in manifest["events"]:
            self.assertFalse(event["full_event"])
            self.assertEqual(len({r['room'] for r in event['rooms']}), len(event['rooms']))
            for item in event["rooms"] + event["resources"]:
                if item["sha256"] in checked: continue
                body = (root / "assets" / (item["sha256"] + ".swf")).read_bytes()
                self.assertEqual(len(body), item["size"])
                self.assertEqual(hashlib.sha256(body).hexdigest(), item["sha256"])
                validate_swf(body)
                checked.add(item["sha256"])
        self.assertGreater(len(checked), 300)


class CatalogueStateTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.WorldTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.catalog = fixture.state / "test-catalog"; (self.catalog / "assets").mkdir(parents=True)
        self.rooms = []
        for room, name in [("100", "town"), ("300", "plaza")]:
            body = fixtures.swf(name.encode()); digest = hashlib.sha256(body).hexdigest()
            (self.catalog / "assets" / (digest + ".swf")).write_bytes(body)
            self.rooms.append({"room": room, "room_key": name, "sha256": digest, "music_id": 9})
        self.companion = fixtures.swf(b"archived-catalog")
        digest = hashlib.sha256(self.companion).hexdigest()
        (self.catalog / "assets" / (digest + ".swf")).write_bytes(self.companion)
        self.event = {"id": "marvel", "name": "Marvel 2012", "full_event": False,
                      "rooms": self.rooms, "resources": [{"scope": "local", "path": "catalogues/party.swf", "sha256": digest}]}
        (self.catalog / "manifest.json").write_text(json.dumps({"events": [self.event]}))
        self.store = WorldStore(fixture.media, fixture.state, catalogue=self.catalog)

    def test_fresh_install_has_designs_without_uploading_or_copying_assets(self):
        assets = self.store.assets()
        self.assertEqual(len(assets), 2)
        self.assertEqual(assets[0]["token"], "catalog/marvel/100")
        self.assertEqual(list((self.fixture.state / "assets").iterdir()), [])
        choice = self.store.selection("100", assets[0]["token"], 9)
        self.assertEqual(self.store.snapshot(), (0, {}))
        self.assertIsNone(self.store.active_event())
        self.assertEqual(self.store.asset_path(*choice["asset"].split("/", 1)).read_bytes(), fixtures.swf(b"town"))

    def test_event_activation_applies_all_rooms_music_and_catalog_and_survives_reopen(self):
        self.store.change("mod", 0, "catalog", event="marvel")
        reopened = WorldStore(self.fixture.media, self.fixture.state, catalogue=self.catalog)
        self.assertEqual(set(reopened.snapshot()[1]), {"100", "300"})
        self.assertEqual(reopened.active_event()["id"], "marvel")
        self.assertEqual(reopened.rooms()["100"]["music_id"], 9)
        self.assertEqual(reopened.resource_file("local", "es", "catalogues/party.swf").read_bytes(), self.companion)
        self.assertEqual(reopened.room_file("town.swf", self.rooms[0]["sha256"]).read_bytes(), fixtures.swf(b"town"))
        reopened.change("mod", 1, "restore_all")
        self.assertIsNone(reopened.active_event())
        self.assertEqual(reopened.rooms(), reopened.baseline())

    def test_missing_resource_rolls_back_whole_event(self):
        (self.catalog / "assets" / (self.rooms[1]["sha256"] + ".swf")).unlink()
        with self.assertRaises(ValueError): self.store.change("mod", 0, "catalog", event="marvel")
        self.assertEqual(self.store.snapshot(), (0, {}))
        self.assertIsNone(self.store.active_event())

    def test_catalogue_cannot_be_used_to_escape_room_or_resource_paths(self):
        for room, token in [("100", "catalog/marvel/300"), ("100", "catalog/../100"), ("100", "catalog/missing/100")]:
            with self.assertRaises(ValueError): self.store.selection(room, token, 0)
        for scope, lang, path in [("local", "en", "../secret.swf"), ("local", "../en", "catalogues/party.swf"), ("global", "en", "C:\\secret.swf")]:
            with self.assertRaises(ValueError): self.store.resource_file(scope, lang, path)

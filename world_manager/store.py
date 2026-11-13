"""Validated media selection and transactional, persistent room settings."""
import hashlib
import io
import json
import re
import sqlite3
import struct
import zlib
import zipfile
from contextlib import contextmanager
from pathlib import Path
from world_manager.catalogue import Catalogue

MAX_UPLOAD = 16 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
LANGUAGES = {"en", "es", "pt", "fr", "ru", "de"}


def validate_swf(body):
    if not 8 <= len(body) <= MAX_UPLOAD or body[:3] not in (b"FWS", b"CWS"):
        raise ValueError("Upload an FWS/CWS SWF file up to 16 MiB.")
    size = struct.unpack_from("<I", body, 4)[0]
    if not 8 <= size <= MAX_EXPANDED:
        raise ValueError("Invalid expanded SWF size (maximum 64 MiB).")
    if body[:3] == b"CWS":
        try:
            decoder = zlib.decompressobj()
            data = decoder.decompress(body[8:], MAX_EXPANDED + 1)
            if not decoder.eof or decoder.unused_data or len(data) != size - 8:
                raise ValueError("The compressed SWF is incomplete or has an invalid size.")
        except zlib.error as exc:
            raise ValueError("The compressed SWF content is invalid.") from exc
    elif len(body) != size:
        raise ValueError("The SWF size does not match its header.")


class WorldStore:
    def __init__(self, media, state, catalogue=None):
        self.media = Path(media).resolve()
        self.state = Path(state).resolve()
        self.catalogue = Catalogue(catalogue)
        self.configs = self.media / "media/play/en/web_service/game_configs"
        if not self.configs.is_dir():
            self.configs = self.media / "play/en/web_service/game_configs"
        self.room_dir = self.media / "media/play/v2/content/global/rooms"
        self.music_dir = self.media / "media/play/v2/content/global/music"
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / "assets").mkdir(exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1), revision INTEGER NOT NULL,
                    overrides TEXT NOT NULL);
                INSERT OR IGNORE INTO settings(id, revision, overrides) VALUES (1, 0, '{}');
                CREATE TABLE IF NOT EXISTS assets (
                    room TEXT NOT NULL, digest TEXT NOT NULL, label TEXT NOT NULL,
                    event TEXT NOT NULL, music INTEGER NOT NULL,
                    PRIMARY KEY (room, digest));
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY, at TEXT DEFAULT CURRENT_TIMESTAMP,
                    actor TEXT NOT NULL, action TEXT NOT NULL, revision INTEGER NOT NULL);
            """)
            if "event_id" not in {row["name"] for row in db.execute("PRAGMA table_info(settings)")}:
                db.execute("ALTER TABLE settings ADD COLUMN event_id TEXT")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.state / "world.sqlite3", timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def baseline(self, language="en", bundled=True):
        if language not in LANGUAGES:
            raise ValueError("Invalid language.")
        if bundled:
            path = self.bundle_path(language)
            if path.is_file():
                with zipfile.ZipFile(path) as archive:
                    return json.loads(archive.read("rooms.json"))
        path = self.media / "media/play" / language / "web_service/game_configs/rooms.json"
        if not path.is_file():
            path = self.media / "play" / language / "web_service/game_configs/rooms.json"
        if not path.is_file():
            path = self.configs / "rooms.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def bundle_path(self, language):
        if language not in LANGUAGES:
            raise ValueError("Invalid language.")
        path = self.media / "media/play" / language / "web_service/game_configs.bin"
        if not path.is_file():
            path = self.media / "media/play/en/web_service/game_configs.bin"
        return path

    def music(self):
        return sorted(int(p.stem) for p in self.music_dir.glob("*.swf") if p.stem.isdecimal())

    def check_room(self, room):
        if room not in self.baseline():
            raise ValueError("This room does not exist in Vanilla.")

    def check_music(self, music):
        try:
            value = int(music)
        except (ValueError, TypeError):
            raise ValueError("Select a valid music track.")
        if value != 0 and not (self.music_dir / (str(value) + ".swf")).is_file():
            raise ValueError("That music file is not available.")
        return value

    def snapshot(self):
        with self.db() as db:
            row = db.execute("SELECT revision, overrides FROM settings WHERE id=1").fetchone()
        return row["revision"], json.loads(row["overrides"])

    def assets(self):
        with self.db() as db:
            uploaded = [dict(row) for row in db.execute("SELECT * FROM assets ORDER BY event, label")]
        for row in uploaded:
            row.update(origin="upload", token="upload/" + row["digest"] + ".swf")
        return uploaded + list(self.catalogue.assets())

    def active_event(self):
        with self.db() as db:
            row = db.execute("SELECT event_id FROM settings WHERE id=1").fetchone()
        return self.catalogue.by_id.get(row["event_id"])

    def upload(self, room, body, label, event, music):
        self.check_room(room)
        music = self.check_music(music)
        label, event = label.strip(), event.strip()
        if not label or not event or len(label) > 80 or len(event) > 80:
            raise ValueError("Design and package names are required (maximum 80 characters).")
        validate_swf(body)
        digest = hashlib.sha256(body).hexdigest()
        # Content-addressed, immutable files; user filenames never become paths.
        path = self.state / "assets" / (digest + ".swf")
        if not path.exists():
            import os
            import tempfile
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
                tmp.write(body)
                temp = Path(tmp.name)
            os.replace(temp, path)
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO assets VALUES (?,?,?,?,?)",
                       (room, digest, label, event, music))
        return digest

    def asset_path(self, kind, filename):
        if kind == "stock":
            allowed = {r["path"] for r in self.baseline().values()}
            if filename not in allowed or Path(filename).name != filename:
                raise ValueError("Invalid original room.")
            path = self.room_dir / filename
        elif kind == "upload" and re.fullmatch(r"[a-f0-9]{64}\.swf", filename):
            path = self.state / "assets" / filename
            if not path.is_file() and any(asset["digest"] == filename[:-4] for asset in self.catalogue.assets()):
                path = self.catalogue.path(filename[:-4])
        else:
            raise ValueError("Invalid resource.")
        if not path.is_file():
            raise ValueError("The room file is not available.")
        return path

    def selection(self, room, asset, music):
        self.check_room(room)
        if asset.startswith("catalog/"):
            parts = asset.split("/")
            if len(parts) != 3 or parts[2] != room:
                raise ValueError("Invalid catalog design.")
            item = self.catalogue.selection(parts[1], room)
            return {"asset": "upload/" + item["sha256"] + ".swf", "music_id": self.check_music(music),
                    "variant": asset, "catalog_id": parts[1], "room_key": item["room_key"]}
        if asset == "original":
            asset = "stock/" + self.baseline()[room]["path"]
        elif not any(a["room"] == room and asset == "upload/" + a["digest"] + ".swf"
                     for a in self.assets()):
            raise ValueError("This design does not belong to this room.")
        self.asset_path(*asset.split("/", 1))
        return {"asset": asset, "music_id": self.check_music(music)}

    def change(self, actor, expected_revision, action, room=None, selection=None, event=None):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision, overrides, event_id FROM settings WHERE id=1").fetchone()
            if str(row["revision"]) != str(expected_revision):
                raise ValueError("Another moderator changed the configuration. Reload the manager.")
            overrides = json.loads(row["overrides"])
            event_id = row["event_id"]
            if action == "save":
                overrides[room] = selection
                if selection.get("catalog_id"):
                    event_id = selection["catalog_id"]
            elif action == "restore":
                overrides.pop(room, None)
            elif action == "restore_all":
                overrides = {}
                event_id = None
            elif action == "catalog":
                preset = self.catalogue.by_id.get(event)
                if not preset or not preset["rooms"]:
                    raise ValueError("The preinstalled package is not available.")
                for resource in preset["resources"]:
                    self.catalogue.path(resource["sha256"])
                overrides = {}
                for item in preset["rooms"]:
                    token = "catalog/" + event + "/" + item["room"]
                    overrides[item["room"]] = self.selection(item["room"], token, item["music_id"])
                event_id = event
            elif action == "event":
                event_id = None
                assets = list(db.execute("SELECT * FROM assets WHERE event=?", (event,)))
                if not assets or len({a["room"] for a in assets}) != len(assets):
                    raise ValueError("The package must contain exactly one design per room.")
                overrides = {}
                for asset in assets:
                    token = "upload/" + asset["digest"] + ".swf"
                    self.check_room(asset["room"])
                    self.asset_path("upload", asset["digest"] + ".swf")
                    overrides[asset["room"]] = {"asset": token, "music_id": self.check_music(asset["music"])}
            else:
                raise ValueError("Invalid action.")
            if not overrides:
                event_id = None
            revision = row["revision"] + 1
            db.execute("UPDATE settings SET revision=?, overrides=?, event_id=? WHERE id=1",
                       (revision, json.dumps(overrides), event_id))
            db.execute("INSERT INTO history(actor,action,revision) VALUES (?,?,?)",
                       (actor, action + ":" + (room or event or "all"), revision))
        return revision

    def rooms(self, language="en", bundled=False):
        rooms = self.baseline(language, bundled=bundled)
        return self.overlay_rooms(rooms)

    def overlay_rooms(self, rooms):
        revision, overrides = self.snapshot()
        for room, value in overrides.items():
            if room in rooms:
                # Keep the SWF in its original directory: relative dependencies
                # inside historical rooms must continue to resolve unchanged.
                token = value["asset"].split("/", 1)[1].removesuffix(".swf") if value["asset"].startswith("upload/") else "original"
                rooms[room]["path"] = rooms[room]["path"] + "?wand_asset={}&wand_revision={}".format(token, revision)
                rooms[room]["music_id"] = value["music_id"]
                if value.get("room_key"):
                    rooms[room]["room_key"] = value["room_key"]
        return rooms

    def bundle(self, language="en"):
        path = self.bundle_path(language)
        if not path.is_file():
            raise ValueError("The configuration bundle is not available.")
        if not self.snapshot()[1]:
            return path.read_bytes()
        output = io.BytesIO()
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(output, "w") as destination:
            for info in source.infolist():
                body = source.read(info.filename)
                if info.filename == "rooms.json":
                    body = json.dumps(self.overlay_rooms(json.loads(body)), separators=(",", ":")).encode()
                destination.writestr(info, body)
        return output.getvalue()

    def room_file(self, filename, token="original"):
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.swf", filename):
            raise ValueError("Invalid resource.")
        if token == "original":
            path = self.room_dir / filename
            if not path.is_file():
                raise ValueError("Room unavailable.")
            return path
        matching = [room for room, data in self.baseline().items() if data["path"] == filename]
        if not any(asset["room"] in matching and asset["digest"] == token for asset in self.assets()):
            raise ValueError("This design does not belong to this room.")
        return self.asset_path("upload", token + ".swf")

    def history(self):
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM history ORDER BY id DESC LIMIT 15")]

    def resource_file(self, scope, language, relative):
        if scope not in ("global", "local") or language not in LANGUAGES:
            raise ValueError("Invalid resource.")
        parts = relative.split("/")
        if any(part in ("", ".", "..") for part in parts) or "\\" in relative or not relative.endswith(".swf"):
            raise ValueError("Invalid resource path.")
        event = self.active_event()
        if event:
            archived = self.catalogue.resource(event["id"], scope, relative)
            if archived:
                return archived
        base = self.media / "media/play/v2/content" / ("global" if scope == "global" else "local/" + language)
        path = base.joinpath(*parts)
        if not path.is_file():
            raise ValueError("Resource unavailable.")
        return path

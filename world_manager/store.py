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

MAX_UPLOAD = 16 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
LANGUAGES = {"en", "es", "pt", "fr", "ru", "de"}


def validate_swf(body):
    if not 8 <= len(body) <= MAX_UPLOAD or body[:3] not in (b"FWS", b"CWS"):
        raise ValueError("Sube un SWF FWS/CWS de hasta 16 MiB.")
    size = struct.unpack_from("<I", body, 4)[0]
    if not 8 <= size <= MAX_EXPANDED:
        raise ValueError("Tamaño SWF descomprimido no válido (máximo 64 MiB).")
    if body[:3] == b"CWS":
        try:
            decoder = zlib.decompressobj()
            data = decoder.decompress(body[8:], MAX_EXPANDED + 1)
            if not decoder.eof or decoder.unused_data or len(data) != size - 8:
                raise ValueError("SWF comprimido incompleto o con tamaño incorrecto.")
        except zlib.error as exc:
            raise ValueError("El contenido comprimido del SWF no es válido.") from exc
    elif len(body) != size:
        raise ValueError("El tamaño del SWF no coincide con su cabecera.")


class WorldStore:
    def __init__(self, media, state):
        self.media = Path(media).resolve()
        self.state = Path(state).resolve()
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
                INSERT OR IGNORE INTO settings VALUES (1, 0, '{}');
                CREATE TABLE IF NOT EXISTS assets (
                    room TEXT NOT NULL, digest TEXT NOT NULL, label TEXT NOT NULL,
                    event TEXT NOT NULL, music INTEGER NOT NULL,
                    PRIMARY KEY (room, digest));
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY, at TEXT DEFAULT CURRENT_TIMESTAMP,
                    actor TEXT NOT NULL, action TEXT NOT NULL, revision INTEGER NOT NULL);
            """)

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
            raise ValueError("Idioma no válido.")
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
            raise ValueError("Idioma no válido.")
        path = self.media / "media/play" / language / "web_service/game_configs.bin"
        if not path.is_file():
            path = self.media / "media/play/en/web_service/game_configs.bin"
        return path

    def music(self):
        return sorted(int(p.stem) for p in self.music_dir.glob("*.swf") if p.stem.isdecimal())

    def check_room(self, room):
        if room not in self.baseline():
            raise ValueError("La sala no existe en Vanilla.")

    def check_music(self, music):
        try:
            value = int(music)
        except (ValueError, TypeError):
            raise ValueError("Selecciona una música válida.")
        if value != 0 and not (self.music_dir / (str(value) + ".swf")).is_file():
            raise ValueError("El archivo de esa música no está disponible.")
        return value

    def snapshot(self):
        with self.db() as db:
            row = db.execute("SELECT revision, overrides FROM settings WHERE id=1").fetchone()
        return row["revision"], json.loads(row["overrides"])

    def assets(self):
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM assets ORDER BY event, label")]

    def upload(self, room, body, label, event, music):
        self.check_room(room)
        music = self.check_music(music)
        label, event = label.strip(), event.strip()
        if not label or not event or len(label) > 80 or len(event) > 80:
            raise ValueError("Nombre y paquete son obligatorios (máximo 80 caracteres).")
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
                raise ValueError("Sala original no válida.")
            path = self.room_dir / filename
        elif kind == "upload" and re.fullmatch(r"[a-f0-9]{64}\.swf", filename):
            path = self.state / "assets" / filename
        else:
            raise ValueError("Recurso no válido.")
        if not path.is_file():
            raise ValueError("El archivo de sala no está disponible.")
        return path

    def selection(self, room, asset, music):
        self.check_room(room)
        if asset == "original":
            asset = "stock/" + self.baseline()[room]["path"]
        elif not any(a["room"] == room and asset == "upload/" + a["digest"] + ".swf"
                     for a in self.assets()):
            raise ValueError("La variante no pertenece a esta sala.")
        self.asset_path(*asset.split("/", 1))
        return {"asset": asset, "music_id": self.check_music(music)}

    def change(self, actor, expected_revision, action, room=None, selection=None, event=None):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision, overrides FROM settings WHERE id=1").fetchone()
            if str(row["revision"]) != str(expected_revision):
                raise ValueError("Otro administrador cambió la configuración. Recarga el panel.")
            overrides = json.loads(row["overrides"])
            if action == "save":
                overrides[room] = selection
            elif action == "restore":
                overrides.pop(room, None)
            elif action == "restore_all":
                overrides = {}
            elif action == "event":
                assets = list(db.execute("SELECT * FROM assets WHERE event=?", (event,)))
                if not assets or len({a["room"] for a in assets}) != len(assets):
                    raise ValueError("El paquete debe contener exactamente una variante por sala.")
                overrides = {}
                for asset in assets:
                    token = "upload/" + asset["digest"] + ".swf"
                    self.check_room(asset["room"])
                    self.asset_path("upload", asset["digest"] + ".swf")
                    overrides[asset["room"]] = {"asset": token, "music_id": self.check_music(asset["music"])}
            else:
                raise ValueError("Acción no válida.")
            revision = row["revision"] + 1
            db.execute("UPDATE settings SET revision=?, overrides=? WHERE id=1",
                       (revision, json.dumps(overrides)))
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
        return rooms

    def bundle(self, language="en"):
        path = self.bundle_path(language)
        if not path.is_file():
            raise ValueError("Paquete de configuración no disponible.")
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
            raise ValueError("Recurso no válido.")
        if token == "original":
            path = self.room_dir / filename
            if not path.is_file():
                raise ValueError("Sala no disponible.")
            return path
        matching = [room for room, data in self.baseline().items() if data["path"] == filename]
        if not any(asset["room"] in matching and asset["digest"] == token for asset in self.assets()):
            raise ValueError("La variante no pertenece a esta sala.")
        return self.asset_path("upload", token + ".swf")

    def history(self):
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM history ORDER BY id DESC LIMIT 15")]

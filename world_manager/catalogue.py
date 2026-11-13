"""Immutable event resources shipped with Wand, available without uploads."""
import json
import re
from pathlib import Path


class Catalogue:
    def __init__(self, root=None):
        self.root = Path(root or Path(__file__).parent / "catalog")
        manifest = self.root / "manifest.json"
        self.events = json.loads(manifest.read_text(encoding="utf-8"))["events"] if manifest.is_file() else []
        self.by_id = {event["id"]: event for event in self.events}

    def path(self, digest):
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid catalog resource.")
        path = self.root / "assets" / (digest + ".swf")
        if not path.is_file():
            raise ValueError("A file is missing from the installed catalog.")
        return path

    def assets(self):
        for event in self.events:
            for room in event["rooms"]:
                yield {"room": room["room"], "digest": room["sha256"], "label": room["room_key"],
                       "event": event["name"], "music": room["music_id"], "origin": "catalog",
                       "token": "catalog/" + event["id"] + "/" + room["room"],
                       "catalog_id": event["id"], "room_key": room["room_key"]}

    def selection(self, event_id, room):
        event = self.by_id.get(event_id)
        if event:
            for asset in event["rooms"]:
                if asset["room"] == room:
                    self.path(asset["sha256"])
                    return asset
        raise ValueError("The design does not belong to this room or event.")

    def resource(self, event_id, scope, path):
        event = self.by_id.get(event_id)
        if event:
            for item in event["resources"]:
                if item["scope"] == scope and item["path"] == path:
                    return self.path(item["sha256"])
        return None

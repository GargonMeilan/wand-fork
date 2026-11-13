"""Render the real manager template for the standalone headless preview check."""
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from world_manager.store import WorldStore

env = Environment(loader=FileSystemLoader(ROOT / "world_manager/templates"),
                  undefined=StrictUndefined, autoescape=select_autoescape(["html"]))
with tempfile.TemporaryDirectory() as state:
    store = WorldStore(ROOT / "vanilla-media", state)
    rooms = store.baseline()
    html = env.get_template("manager/world.html").render(
        rooms=rooms, room="100", selected=rooms["100"],
        current={"asset": "original", "music_id": rooms["100"]["music_id"]},
        variants=[a for a in store.assets() if a["room"] == "100"],
        music=store.music(), csrf="preview-fixture", revision=0, overrides={},
        events=[], catalogue=store.catalogue.events, active_event=None,
        history=[], error="", saved=False)
    output = ROOT / ".validation/catalog-ui.html"
    output.parent.mkdir(exist_ok=True)
    output.write_text(html, encoding="utf-8")

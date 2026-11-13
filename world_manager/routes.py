"""Dash/Sanic integration. Public routes only expose validated game resources."""
import hmac
import json
import os
import secrets
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

from jinja2 import ChoiceLoader, FileSystemLoader
from sanic import Blueprint, response
from sqlalchemy import func

import dash
from dash import app, env
from dash.data.penguin import Penguin
from dash.routes.manager.login import login_auth
from world_manager.store import MAX_UPLOAD, WorldStore
from world_manager.presence import read_presence

here = Path(__file__).resolve().parent
world = Blueprint("wand_world")


def store():
    return app.ctx.world_store


def moderator(handler):
    @login_auth()
    @wraps(handler)
    async def guarded(request, *args, **kwargs):
        user = await Penguin.query.where(
            func.lower(Penguin.username) == request.ctx.session.get("username")).gino.first()
        if user is None or not user.moderator:
            return response.text("A moderator account is required.", status=403)
        if request.method == "POST":
            expected = request.ctx.session.get("world_csrf", "")
            supplied = request.form.get("csrf", "")
            if not expected or not isinstance(supplied, str) or not hmac.compare_digest(expected.encode(), supplied.encode()):
                return response.text("Your session expired. Reload the manager.", status=403)
        return await handler(request, *args, **kwargs)
    return guarded


@world.get("/manager/world")
@moderator
async def panel(request):
    return render_panel(request)


@world.get("/manager/world/preview")
@moderator
async def preview(request):
    room = request.args.get("room", "100")
    token = request.args.get("asset", "original")
    try:
        store().selection(room, token, 0)
    except ValueError as exc:
        return response.text(str(exc), status=400)
    source = "/manager/world/preview-file?" + urlencode({"room": room, "asset": token})
    return response.html(env.get_template("manager/preview.html").render(
        room_name=store().baseline()[room]["name"], source=source), headers={"Cache-Control": "no-store"})


@world.get("/manager/world/preview-file")
@moderator
async def preview_file(request):
    room = request.args.get("room", "100")
    try:
        selection = store().selection(room, request.args.get("asset", "original"), 0)
        path = store().asset_path(*selection["asset"].split("/", 1))
    except ValueError as exc:
        return response.text(str(exc), status=400)
    return await response.file(str(path), mime_type="application/x-shockwave-flash", headers={"Cache-Control": "no-store"})


@world.get("/manager/online")
@moderator
async def online_panel(request):
    return response.html(env.get_template("manager/online.html").render(),
                         headers={"Cache-Control": "no-store"})


@world.get("/manager/online/data")
@moderator
async def online_data(request):
    try:
        data = await read_presence(app.ctx.redis)
    except Exception:
        return response.json({"error": "Presence could not be loaded. Retrying automatically."},
                             status=503, headers={"Cache-Control": "no-store"})
    return response.json(data, headers={"Cache-Control": "no-store"})


def render_panel(request, error="", status=200):
    rooms = store().baseline()
    room = request.args.get("room", "100")
    if room not in rooms:
        return response.text("Unknown room.", status=404)
    csrf = request.ctx.session.setdefault("world_csrf", secrets.token_urlsafe(32))
    revision, overrides = store().snapshot()
    assets = store().assets()
    groups = {}
    for asset in assets:
        if asset.get("origin") == "upload":
            groups.setdefault(asset["event"], []).append(asset)
    events = [{"name": name, "count": len(values),
               "valid": len({a['room'] for a in values}) == len(values)}
              for name, values in sorted(groups.items())]
    current = overrides.get(room, {"asset": "original", "music_id": rooms[room]["music_id"]})
    if current["asset"].startswith("stock/"):
        current = dict(current, asset="original")
    template = env.get_template("manager/world.html")
    audit_file = here / "event-audit.json"
    audit = json.loads(audit_file.read_text(encoding="utf-8")) if audit_file.is_file() else {"events": []}
    html = template.render(rooms=rooms, room=room, selected=rooms[room], current=current,
                           variants=[a for a in assets if a["room"] == room],
                           music=store().music(), csrf=csrf, revision=revision,
                           overrides=overrides, events=events, audit=audit,
                           catalogue=store().catalogue.events, active_event=store().active_event(),
                           history=store().history(), error=error,
                           saved=request.args.get("saved") == "1")
    return response.html(html, status=status, headers={"Cache-Control": "no-store"})


@world.post("/manager/world")
@moderator
async def update(request):
    action = request.form.get("action", "")
    room = request.form.get("room", "")
    try:
        if action == "upload":
            upload = request.files.get("swf")
            if upload is None or len(upload.body) > MAX_UPLOAD:
                raise ValueError("Select a SWF file up to 16 MiB.")
            store().upload(room, upload.body, request.form.get("label", ""),
                           request.form.get("event", ""), request.form.get("music", ""))
        else:
            selection = None
            if action in ("save", "restore"):
                store().check_room(room)
            if action == "save":
                selection = store().selection(room, request.form.get("asset", ""),
                                              request.form.get("music", ""))
            store().change(request.ctx.session["username"], request.form.get("revision", ""),
                           action, room=room, selection=selection,
                           event=request.form.get("event", ""))
    except ValueError as exc:
        # Preserve the selected room without trusting submitted template paths.
        return response.html(env.get_template("manager/world-error.html").render(error=str(exc)),
                             status=400, headers={"Cache-Control": "no-store"})
    return response.redirect("/manager/world?" + urlencode({"room": room or "100", "saved": "1"}), status=303)


@world.get("/world/revision")
async def revision(request):
    number, _ = store().snapshot()
    return response.json({"revision": number}, headers={"Cache-Control": "no-store"})


@world.get("/world/rooms/<language>/<format>")
async def rooms(request, language, format):
    if format not in ("json", "jsonp"):
        return response.text("Not found", status=404)
    try:
        data = store().rooms(language)
    except ValueError:
        return response.text("Not found", status=404)
    headers = {"Cache-Control": "no-store"}
    if format == "jsonp":
        return response.text("cp_rooms(" + json.dumps(data) + ");",
                             content_type="application/javascript", headers=headers)
    return response.json(data, headers=headers)


@world.get("/world/room-file/<filename>")
async def asset(request, filename):
    try:
        token = request.args.get("wand_asset", "original")
        path = store().room_file(filename, token)
    except ValueError:
        return response.text("Not found", status=404)
    return await response.file(str(path), mime_type="application/x-shockwave-flash",
                               headers={"Cache-Control": "no-store" if token == "original" else "public, max-age=31536000, immutable",
                                        "X-Content-Type-Options": "nosniff"})


@world.get("/world/config-bundle/<language>")
async def config_bundle(request, language):
    try:
        body = store().bundle(language)
    except ValueError:
        return response.text("Not found", status=404)
    return response.raw(body, content_type="application/octet-stream",
                        headers={"Cache-Control": "no-store"})


@world.get("/world/event-resource/<scope>/<language>/<relative:path>")
async def event_resource(request, scope, language, relative):
    try:
        path = store().resource_file(scope, language, relative)
    except ValueError:
        return response.text("Not found", status=404)
    return await response.file(str(path), mime_type="application/x-shockwave-flash",
                               headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


def install():
    app.config.REQUEST_MAX_SIZE = min(app.config.REQUEST_MAX_SIZE, MAX_UPLOAD + 1024 * 1024)
    env.loader = ChoiceLoader([FileSystemLoader(str(here / "templates")), env.loader])
    # Sanic 21.12 appends its own slash before the file wildcard. A trailing
    # slash here registers //file and makes normal browser URLs return 404.
    world.static("/manager/world-static", str(here / "static"))
    world.static("/manager/static", str(Path(dash.__file__).parent / "routes/manager/static"),
                 name="manager_assets")
    app.blueprint(world)

    @app.listener("before_server_start")
    async def start_world(sanic, loop):
        sanic.ctx.world_store = WorldStore(os.environ.get("WAND_VANILLA_ROOT", "/opt/wand/vanilla"),
                                           os.environ.get("WAND_WORLD_STATE", "/var/lib/wand-world"))

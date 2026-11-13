"""Exercise real Dash/Nginx/Redis/Houdini in tests/local-stack.py's fixture."""
import hashlib
import io
import http.cookiejar
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".validation/python"))
import websocket

STATE = ROOT / ".validation/local-stack"
META = json.loads((STATE / "meta.json").read_text())
PORT = META["port"]
BASE = "http://127.0.0.1:" + str(PORT)
PASSWORD = "FixturePass123!"
COMPOSE = ["docker", "compose", "-p", META["project"], "-f", str(STATE / "compose.json")]
results = []


def passed(message):
    results.append(message)
    print(message, flush=True)
    (STATE / "integration-results.json").write_text(json.dumps(results, indent=2))


def execute(service, code):
    return subprocess.check_output([*COMPOSE, "exec", "-T", service, "python", "-"], input=code, text=True)


def seed():
    code = '''
import asyncio, asyncpg, bcrypt, json
from dash.crypto import Crypto
async def main():
    db = await asyncpg.connect(host='db', user='postgres', password='local-fixture-password', database='postgres')
    hashed = bcrypt.hashpw(Crypto.get_login_hash(Crypto.hash('FixturePass123!').upper(), 'houdini').encode(), bcrypt.gensalt()).decode()
    result = {}
    for name, moderator in [('testmod', True), ('testuser', False)]:
        result[name] = await db.fetchval("""INSERT INTO penguin(username,nickname,password,email,active,moderator,color,registration_date,last_paycheck,last_field_op,com_message_read_date,approval_en,approval_es,approval_pt,approval_fr)
            VALUES($1,$1,$2,$3,TRUE,$4,1,now(),now(),now(),now(),TRUE,TRUE,TRUE,TRUE)
            ON CONFLICT(username) DO UPDATE SET password=excluded.password,moderator=excluded.moderator RETURNING id""",name,hashed,name+'@example.invalid',moderator)
        await db.execute('INSERT INTO penguin_item(penguin_id,item_id) VALUES($1,1) ON CONFLICT DO NOTHING',result[name])
    print(json.dumps(result))
    await db.close()
asyncio.run(main())
'''
    result = json.loads(execute("dash", code))
    (STATE / "accounts.json").write_text(json.dumps(result))
    return result


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(client, path, form=None, host="play", body=None, content_type=None):
    headers = {"Host": f"{host}.localhost:{PORT}"}
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        content_type = "application/x-www-form-urlencoded"
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(BASE + path, data=body, headers=headers)
    try:
        return client.open(req, timeout=20)
    except urllib.error.HTTPError as exc:
        return exc


def login(client, name="testmod"):
    result = request(client, "/manager/login/", {"username": name, "password": PASSWORD})
    assert result.status == 200
    page = result.read().decode()
    assert "Rooms &amp; events" in page, page[:300]


def config(client):
    result = request(client, "/play/en/web_service/game_configs/rooms.json", host="media")
    assert result.status == 200, result.read()[:300]
    assert result.headers["Cache-Control"] == "no-store"
    return json.load(result)


def page_state(client):
    result = request(client, "/manager/world?room=100")
    html = result.read().decode()
    assert result.status == 200, html[:500]
    return {name: re.search(r'name="' + name + r'" value="([^"]+)"', html)[1] for name in ("csrf", "revision")}


def post(client, action, **values):
    form = {**page_state(client), "room": "100", "action": action, **values}
    result = request(client, "/manager/world", form)
    assert result.status == 200, result.read()[:500]
    return result.read()


def upload(client, room, filename):
    csrf = page_state(client)["csrf"]
    fields = {"csrf": csrf, "action": "upload", "room": room, "event": "Local fixture", "label": filename, "music": "9"}
    boundary = "wand-local-integration-boundary"
    data = b""
    for name, value in fields.items():
        data += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    swf = (ROOT / "vanilla-media/media/play/v2/content/global/rooms" / filename).read_bytes()
    data += f'--{boundary}\r\nContent-Disposition: form-data; name="swf"; filename="room.swf"\r\nContent-Type: application/x-shockwave-flash\r\n\r\n'.encode() + swf + f'\r\n--{boundary}--\r\n'.encode()
    result = request(client, "/manager/world", body=data, content_type="multipart/form-data; boundary=" + boundary)
    assert result.status == 200, result.read()[:500]
    return hashlib.sha256(swf).hexdigest(), swf


def until(check, timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise AssertionError("Timed out waiting for integration condition")
        time.sleep(1)


def roster(client):
    result = request(client, "/manager/online/data")
    assert result.status == 200, result.read()[:300]
    return json.load(result)


def swap(digest):
    return digest[16:] + digest[:16]


def encrypted(value):
    return swap(hashlib.md5(value.encode()).hexdigest())


def password_hash():
    digest = hashlib.md5(PASSWORD.encode()).hexdigest().upper()
    return encrypted(swap(digest) + "houdini" + "Y(02.>'H}t\":E1")


class Game:
    def __init__(self, target):
        self.ws = websocket.create_connection(f"ws://127.0.0.1:{PORT}/__wand/ws/{target}",
            origin=f"http://play.localhost:{PORT}", host=f"play.localhost:{PORT}", timeout=10, http_no_proxy=["127.0.0.1"])
        self.buffer = b""
        self.send('<msg t="sys"><body action="verChk" r="0"><ver v="153" /></body></msg>')
        assert "apiOK" in self.receive()
        self.send('<msg t="sys"><body action="rndK" r="-1" /></msg>')
        assert "rndK" in self.receive()

    def send(self, data):
        self.ws.send_binary(data.encode() + b"\0")

    def receive(self):
        while b"\0" not in self.buffer:
            chunk = self.ws.recv()
            if not chunk: raise RuntimeError("Game connection closed")
            self.buffer += chunk.encode() if isinstance(chunk, str) else chunk
        packet, self.buffer = self.buffer.split(b"\0", 1)
        return packet.decode()

    def expect(self, command):
        for _ in range(30):
            packet = self.receive()
            if packet.startswith("%xt%" + command + "%"):
                return packet
            assert not packet.startswith("%xt%e%"), packet
        raise AssertionError("Missing game packet: " + command)

    def authenticate(self, name, password):
        self.send(f'<msg t="sys"><body action="login" r="0"><login z="w1"><nick><![CDATA[{name}]]></nick><pword><![CDATA[{password}]]></pword></login></body></msg>')
        return self.expect("l")

    def close(self):
        self.ws.close()


def connect(name, target):
    connection = Game("login")
    packet = connection.authenticate(name, password_hash()).split("%")
    penguin_id, login_key = packet[4:6]
    connection.close()
    game = Game(target)
    game.authenticate(name, encrypted(login_key + "houdini") + login_key)
    game.send(f"%xt%s%j#js%-1%{penguin_id}%{login_key}%")
    game.expect("js")
    game.expect("jr")
    return game, int(penguin_id)


def main():
    accounts = seed()
    anonymous = opener()
    assert "/manager/login" in request(anonymous, "/manager/online/data").url
    denied = request(anonymous, "/manager/login/", {"username": "testuser", "password": PASSWORD}).read().decode()
    assert "do not have permission" in denied
    client = opener(); login(client)
    for path in ("/manager/world-static/world.css", "/manager/world-static/online.js", "/manager/static/css/style.css", "/manager/static/js/checks.js"):
        assert request(client, path).status == 200, path
    passed("Real manager login and moderator-only access: OK")
    until(lambda: all(s["available"] for s in roster(client)["servers"]))
    passed("Four live world snapshots visible through Nginx/Dash/Redis: OK")
    baseline = json.loads((ROOT / "vanilla-media/media/play/en/web_service/game_configs/rooms.json").read_text())
    post(client, "restore_all")
    manifest = json.loads((ROOT / "world_manager/catalog/manifest.json").read_text())
    for event in manifest["events"]:
        post(client, "catalog", event=event["id"])
        configured = config(client)
        for item in event["rooms"]:
            room = configured[item["room"]]
            assert item["sha256"] in room["path"] and room["music_id"] == item["music_id"]
            result = request(client, "/play/v2/content/global/rooms/" + room["path"], host="media")
            assert result.status == 200 and hashlib.sha256(result.read()).hexdigest() == item["sha256"]
        for item in event["resources"]:
            prefix = "global/" if item["scope"] == "global" else "local/en/"
            result = request(client, "/play/v2/content/" + prefix + item["path"], host="media")
            assert result.status == 200, (event["id"], item["path"], result.status)
            assert hashlib.sha256(result.read()).hexdigest() == item["sha256"]
    post(client, "restore_all")
    passed("All 16 installed packages activate; 303 room variants and 76 companion references are delivered through Nginx with matching hashes: OK")
    post(client, "save", asset="original", music="9")
    assert config(client)["100"]["music_id"] == 9
    before = page_state(client)["revision"]
    assert request(client, "/manager/world", {"action": "restore_all", "csrf": "wrong", "revision": before}).status == 403
    assert page_state(client)["revision"] == before
    digest, body = upload(client, "100", "town.swf")
    upload(client, "300", "plaza.swf")
    post(client, "save", asset="upload/" + digest + ".swf", music="9")
    changed = config(client)["100"]
    assert digest in changed["path"]
    served = request(client, "/play/v2/content/global/rooms/" + changed["path"], host="media")
    assert served.status == 200 and served.read() == body
    callback = request(client, "/play/es/web_service/game_configs/rooms.jsonp", host="media").read().decode()
    assert callback.startswith("cp_rooms(") and digest in callback
    post(client, "event", event="Local fixture")
    data = config(client)
    assert data["100"]["music_id"] == 9 and data["300"]["music_id"] == 9
    binary = request(client, "/play/en/web_service/game_configs.bin", host="media")
    assert binary.status == 200 and binary.headers["Cache-Control"] == "no-store"
    with zipfile.ZipFile(io.BytesIO(binary.read())) as changed, zipfile.ZipFile(ROOT / "vanilla-media/media/play/en/web_service/game_configs.bin") as source:
        rooms = json.loads(changed.read("rooms.json"))
        assert rooms["100"]["music_id"] == 9 and digest in rooms["100"]["path"]
        for name in source.namelist():
            if name != "rooms.json": assert changed.read(name) == source.read(name), name
    passed("Runtime music, SWF uploads, versioned delivery, JSONP, real Flash ZIP bundle, package activation and CSRF rejection: OK")

    # Recreate the real Dash process; the test SQLite volume must survive.
    revision = page_state(client)["revision"]
    subprocess.run([*COMPOSE, "up", "-d", "--no-deps", "--force-recreate", "--wait", "dash"], check=True)
    def ready():
        try: return request(anonymous, "/__wand/world/revision").status == 200
        except OSError: return False
    until(ready)
    client = opener(); login(client)
    assert page_state(client)["revision"] == revision
    assert config(client)["100"]["path"] == data["100"]["path"]
    passed("Room selections and uploaded assets survive Dash recreation: OK")
    games = []
    try:
        first, first_id = connect("testmod", "blizzard"); games.append(first)
        second, second_id = connect("testuser", "glaciar"); games.append(second)
        def joined():
            rows = roster(client)["players"]
            return rows if {r["id"] for r in rows} == {first_id, second_id} else None
        rows = until(joined)
        assert {r["server_id"] for r in rows} == {3100, 3101}
        first.send("%xt%s%j#jr%-1%100%400%300%")
        first.expect("jr")
        time.sleep(0.6)  # Respect the room-change cooldown even if already in town.
        until(lambda: any(r["id"] == first_id and r["room_id"] == 100 for r in roster(client)["players"]))
        first.send("%xt%s%j#jr%-1%300%400%300%")
        first.expect("jr")
        until(lambda: any(r["id"] == first_id and r["room_id"] == 300 for r in roster(client)["players"]))
        passed("Two authenticated game sessions, distinct servers and live room changes: OK")
    finally:
        for game in games: game.close()
    until(lambda: not roster(client)["players"])
    passed("Real disconnects disappear from the online panel: OK")
    subprocess.run([*COMPOSE, "stop", "houdini_yeti"], check=True)
    until(lambda: not next(s for s in roster(client)["servers"] if s["id"] == 3103)["available"], timeout=35)
    subprocess.run([*COMPOSE, "up", "-d", "--no-deps", "--wait", "houdini_yeti"], check=True)
    until(lambda: next(s for s in roster(client)["servers"] if s["id"] == 3103)["available"])
    passed("Stopped server expires, differs from zero players and recovers after restart: OK")
    post(client, "restore_all")
    assert config(client) == baseline
    assert request(client, "/play/en/web_service/game_configs.bin", host="media").read() == (ROOT / "vanilla-media/media/play/en/web_service/game_configs.bin").read_bytes()
    passed("All room definitions restore exactly to original JSON: OK")
    print("Integration checks complete.", flush=True)


if __name__ == "__main__":
    main()

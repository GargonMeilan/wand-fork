"""Disposable Nginx -> Websockify -> TCP integration, without any Wand data."""
import contextlib
from pathlib import Path
import socketserver
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs


def fixture():
    class Registration(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            fields = parse_qs(body.decode())
            valid = self.path == "/create/legacy/" and fields == {
                "action": ["validate_agreement"], "agree_to_rules": ["1"], "agree_to_terms": ["1"]}
            self.send_response(200 if valid else 400)
            self.end_headers()
            self.wfile.write(b"success=1" if valid else b"wrong-route-or-body")

    http = ThreadingHTTPServer(("0.0.0.0", 3000), Registration)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    class Echo(socketserver.BaseRequestHandler):
        def handle(self):
            while data := self.request.recv(65536):
                self.request.sendall(str(self.server.server_address[1]).encode() + b":" + data)

    for port in (7112, 9875, 9876, 9877, 9878):
        server = socketserver.ThreadingTCPServer(("0.0.0.0", port), Echo)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Event().wait()


def check():
    import websocket
    import urllib.request

    prefix = "wand-ruffle-test-" + uuid.uuid4().hex[:10]
    network = prefix + "-network"
    containers = []

    def docker(*args):
        return subprocess.check_output(["docker", *args], text=True).strip()

    def run(name, *args):
        containers.append(name)
        return docker("run", "-d", "--name", name, "--network", network, *args)

    try:
        docker("network", "create", network)
        run(prefix + "-tcp", "--network-alias", "dash", "--network-alias", "houdini_login", "--network-alias", "houdini_blizzard",
            "--network-alias", "houdini_glaciar", "--network-alias", "houdini_avalanche", "--network-alias", "houdini_yeti",
            "-v", f"{Path.cwd()}/tests:/tests:ro", "--entrypoint", "python", "wand-websocket-test", "/tests/check-proxy-chain.py", "fixture")
        run(prefix + "-ws", "--network-alias", "websocket", "--read-only", "--tmpfs", "/tmp:size=1m,mode=1777",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "-e", "WEB_LEGACY_PLAY=http://old.example.test",
            "-e", "WEB_VANILLA_PLAY=http://play.example.test",
            "-e", "GAME_LOGIN_PORT=7112", "wand-websocket-test")
        web = prefix + "-web"
        run(web, "-p", "127.0.0.1::80",
            "-e", "WEB_LEGACY_PLAY=http://old.example.test", "-e", "WEB_LEGACY_MEDIA=http://legacy.example.test",
            "-e", "WEB_VANILLA_PLAY=http://play.example.test", "-e", "WEB_VANILLA_MEDIA=http://media.example.test",
            "-v", f"{Path.cwd()}/templates:/t:ro", "--entrypoint", "sh", "wand-ruffle-web-test", "-ec",
            "rm /etc/nginx/conf.d/default.conf; dockerize -template /t/sites/legacy.conf.template:/etc/nginx/conf.d/legacy.conf -template /t/sites/vanilla.conf.template:/etc/nginx/conf.d/vanilla.conf; exec nginx -g 'daemon off;'")
        address = docker("port", web, "80/tcp")
        url = f"ws://{address}/__wand/ws/"
        deadline = time.monotonic() + 20
        for name, port in (("login", 7112), ("blizzard", 9875), ("glaciar", 9876), ("avalanche", 9877), ("yeti", 9878)):
            while True:
                try:
                    ws = websocket.create_connection(url + name, origin="http://old.example.test", host="old.example.test", timeout=3)
                    packet = b'<msg t="sys"><body action="rndK" r="-1" /></msg>\x00%xt%heartbeat%\x00'
                    ws.send_binary(packet)
                    expected = str(port).encode() + b":" + packet
                    received = b""
                    while len(received) < len(expected):
                        received += ws.recv()
                    assert received == expected, (name, received)
                    ws.close()
                    break
                except (OSError, websocket.WebSocketException):
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.1)
            print(f"Nginx -> Websockify -> {name}:{port}: OK")
        try:
            ws = websocket.create_connection(url + "login", origin="https://foreign.example.test", host="old.example.test", timeout=3)
            ws.close()
            raise AssertionError("Foreign origin accepted by Nginx")
        except websocket.WebSocketBadStatusException as error:
            assert error.status_code == 403
        print("Nginx origin rejection: OK")
        for name, port in (("login", 7112), ("blizzard", 9875), ("glaciar", 9876), ("avalanche", 9877), ("yeti", 9878)):
            ws = websocket.create_connection(url + name, origin="http://play.example.test", host="play.example.test", timeout=3)
            ws.send_binary(b"vanilla\0")
            selftest = ws.recv()
            assert selftest == str(port).encode() + b":vanilla\0", selftest
            ws.close()
            print(f"Vanilla Nginx -> Websockify -> {name}:{port}: OK")
        for host in ("old.example.test", "legacy.example.test"):
            request = urllib.request.Request(f"http://{address}/create_account/create_account.php",
                data=b"action=validate_agreement&agree_to_rules=1&agree_to_terms=1",
                headers={"Host": host, "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(request, timeout=3) as response:
                assert response.status == 200 and response.read() == b"success=1"
            print(f"Legacy agreement POST via {host}, canonical upstream and body: OK")
    except BaseException:
        for name in containers:
            subprocess.run(["docker", "logs", name], check=False)
        raise
    finally:
        for name in reversed(containers):
            subprocess.run(["docker", "rm", "-f", name], check=False, stdout=subprocess.DEVNULL)
        with contextlib.suppress(subprocess.CalledProcessError):
            docker("network", "rm", network)


if __name__ == "__main__":
    fixture() if sys.argv[1:] == ["fixture"] else check()

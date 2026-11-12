"""Real Websockify binary framing test; no game database or Docker required.

pip install -r websocket/requirements.txt websocket-client==1.9.0
python -m unittest discover -s tests -p 'test_*.py' -v
"""
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import websocket

spec = importlib.util.spec_from_file_location("wand_proxy", Path("websocket/start.py"))
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


class ProxyTest(unittest.TestCase):
    def test_production_destinations(self):
        origin, targets = proxy.configuration({"WEB_LEGACY_PLAY": "https://old.example.test/play", "GAME_LOGIN_PORT": "7112"})
        self.assertEqual(origin, "https://old.example.test")
        self.assertEqual(targets, {"login": "houdini_login:7112", "blizzard": "houdini_blizzard:9875",
                                  "glaciar": "houdini_glaciar:9876", "avalanche": "houdini_avalanche:9877", "yeti": "houdini_yeti:9878",
                                  "snow": "snowflake:7002"})

    def test_snow_uses_fixed_internal_host_and_configured_port(self):
        _, targets = proxy.configuration({"WEB_LEGACY_PLAY": "https://old.example.test", "SNOWFLAKE_PORT": "17002"})
        self.assertEqual(targets["snow"], "snowflake:17002")
        with self.assertRaises(ValueError):
            proxy.configuration({"WEB_LEGACY_PLAY": "https://old.example.test", "SNOWFLAKE_PORT": "65536"})

    def test_invalid_configuration(self):
        for value in ("not-a-url", "ftp://old.example.test", "https://user:password@old.example.test"):
            with self.assertRaises(ValueError):
                proxy.configuration({"WEB_LEGACY_PLAY": value})
        with self.assertRaises(ValueError):
            proxy.configuration({"WEB_LEGACY_PLAY": "https://old.example.test", "GAME_LOGIN_PORT": "0"})

    def test_vanilla_origin_is_explicitly_allowed(self):
        origins, _ = proxy.configuration({"WEB_LEGACY_PLAY": "https://old.example.test", "WEB_VANILLA_PLAY": "https://play.example.test/es"})
        self.assertEqual(origins.split(), ["https://old.example.test", "https://play.example.test"])
        with self.assertRaises(ValueError):
            proxy.configuration({"WEB_LEGACY_PLAY": "https://old.example.test", "WEB_VANILLA_PLAY": "ftp://play.example.test"})

    def exchange(self, origin, token="login", reject=False):
        with socket.socket() as target, tempfile.TemporaryDirectory() as tmp:
            target.bind(("127.0.0.1", 0))
            target.listen()
            target.settimeout(4)
            accepted = []

            def echo():
                try:
                    conn, _ = target.accept()
                    accepted.append(True)
                    with conn:
                        while data := conn.recv(4096):
                            conn.sendall(data)
                except (TimeoutError, OSError):
                    pass

            worker = threading.Thread(target=echo, daemon=True)
            worker.start()
            token_file = Path(tmp) / "tokens.txt"
            token_file.write_text(f"login: 127.0.0.1:{target.getsockname()[1]}\n")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            command = [sys.executable, "-m", "websockify", "--run-once", "--token-plugin", "ReadOnlyTokenFile",
                       "--token-source", str(token_file), "--auth-plugin", "ExpectOrigin", "--auth-source",
                       "https://old.example.test", f"127.0.0.1:{port}"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while True:
                    try:
                        ws = websocket.create_connection(f"ws://127.0.0.1:{port}/?token={token}",
                                                         origin=origin, timeout=3, http_no_proxy=["127.0.0.1"])
                        break
                    except ConnectionRefusedError:
                        if time.monotonic() > deadline:
                            raise
                        time.sleep(0.05)
                    except websocket.WebSocketBadStatusException as error:
                        self.assertTrue(reject)
                        self.assertEqual(error.status_code, 403)
                        self.assertEqual(accepted, [])
                        return
                    except websocket.WebSocketConnectionClosedException:
                        # Websockify 0.13 closes the handshake for an unknown token.
                        self.assertTrue(reject)
                        self.assertNotEqual(token, "login")
                        self.assertEqual(accepted, [])
                        return
                self.assertFalse(reject)
                payload = b'<msg t="sys"><body action="verChk" r="0"><ver v="153" /></body></msg>\x00%xt%j#js%-1%123%key%\x00'
                ws.send_binary(payload)
                received = b""
                while len(received) < len(payload):
                    received += ws.recv()
                self.assertEqual(received, payload)
                ws.close()
            finally:
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                target.close()
                worker.join(timeout=5)

    def test_binary_xml_and_xt_roundtrip(self):
        self.exchange("https://old.example.test")

    def test_foreign_origin_rejected(self):
        self.exchange("https://foreign.example.test", reject=True)

    def test_unknown_destination_rejected(self):
        self.exchange("https://old.example.test", token="arbitrary-host", reject=True)

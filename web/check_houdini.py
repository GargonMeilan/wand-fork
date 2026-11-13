"""Readiness without logging in or accessing a user's account.

Houdini opens its TCP port before loading database-backed handlers. Require a
successful version handshake, rather than accepting an open TCP port alone.
"""
import socket
import sys
from xml.etree import ElementTree


def ready(port):
    with socket.create_connection(("127.0.0.1", int(port)), timeout=2) as connection:
        connection.settimeout(2)
        connection.sendall(b'<msg t="sys"><body action="verChk" r="0"><ver v="153" /></body></msg>\0')
        data = b""
        while b"\0" not in data and len(data) < 8192:
            chunk = connection.recv(1024)
            if not chunk:
                return False
            data += chunk
        body = ElementTree.fromstring(data.split(b"\0", 1)[0]).find("body")
        return body is not None and body.get("action") == "apiOK"


if __name__ == "__main__":
    try:
        sys.exit(0 if ready(sys.argv[1]) else 1)
    except (OSError, ValueError, ElementTree.ParseError):
        sys.exit(1)

"""Fixed destinations only: the browser cannot choose arbitrary TCP targets."""
import os
from pathlib import Path
from urllib.parse import urlsplit


def configuration(environment):
    play = urlsplit(environment["WEB_LEGACY_PLAY"])
    if play.scheme not in ("http", "https") or not play.hostname or play.username or play.password:
        raise ValueError("WEB_LEGACY_PLAY must be an absolute HTTP(S) URL without credentials")
    origin = f"{play.scheme}://{play.netloc}"
    port = int(environment.get("GAME_LOGIN_PORT", "6112"))
    if not 1 <= port <= 65535:
        raise ValueError("GAME_LOGIN_PORT must be between 1 and 65535")
    targets = {"login": f"houdini_login:{port}"}
    targets.update({name: f"houdini_{name}:{port}" for name, port in (
        ("blizzard", 9875), ("glaciar", 9876), ("avalanche", 9877), ("yeti", 9878)
    )})
    return origin, targets


if __name__ == "__main__":
    origin, targets = configuration(os.environ)
    token_file = Path("/tmp/wand-sockets.txt")
    token_file.write_text("".join(f"{key}: {value}\n" for key, value in targets.items()))
    os.execvp("websockify", [
        "websockify", "--token-plugin", "ReadOnlyTokenFile", "--token-source", str(token_file),
        "--auth-plugin", "ExpectOrigin", "--auth-source", origin, "0.0.0.0:8080",
    ])

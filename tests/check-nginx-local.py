"""Run the existing Nginx shell assertions from Windows without shell path conversion."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
meta = json.loads((ROOT / ".validation/local-stack/meta.json").read_text())
script = (ROOT / "tests/check-nginx.sh").read_text()
body = re.search(r"--entrypoint sh wand-ruffle-web-test -ec '([\s\S]*)'\s*done", script)[1]
for scenario in ("domains", "paths", "shared", "flash", "captcha"):
    env = {"WEB_LEGACY_PLAY": "http://old.example.test", "WEB_LEGACY_MEDIA": "http://legacy.example.test",
           "WEB_VANILLA_PLAY": "http://play.example.test", "WEB_VANILLA_MEDIA": "http://media.example.test",
           "VANILLA_PLAYER": "flash" if scenario == "flash" else "ruffle",
           "LEGACY_PLAYER": "flash" if scenario == "flash" else "ruffle",
           "GAME_ADDRESS": "game.example.test", "GAME_LOGIN_PORT": "7112",
           "SNOWFLAKE_HOST": "snow.example.test", "SNOWFLAKE_PORT": "7002",
           "WEB_RECAPTCHA_SITE": "example-site-key" if scenario == "captcha" else ""}
    if scenario == "paths":
        env.update(WEB_LEGACY_PLAY="http://old.example.test/game", WEB_LEGACY_MEDIA="http://legacy.example.test/assets",
                   WEB_VANILLA_PLAY="http://play.example.test/game", WEB_VANILLA_MEDIA="http://media.example.test/assets")
    elif scenario == "shared":
        env.update(WEB_LEGACY_PLAY="http://old.example.test/game", WEB_LEGACY_MEDIA="http://old.example.test/media",
                   WEB_VANILLA_PLAY="http://play.example.test/game", WEB_VANILLA_MEDIA="http://play.example.test/media")
    command = ["docker", "run", "--rm", "--add-host", "dash:127.0.0.1"]
    for name, value in env.items():
        command += ["-e", name + "=" + value]
    command += ["-v", f"{ROOT}/templates:/t:ro", "--entrypoint", "sh", meta["project"] + "-web", "-ec", body]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        print(result.stdout, result.stderr)
        result.check_returncode()
    print("Nginx configuration, static routes and WASM MIME: " + scenario + " OK", flush=True)

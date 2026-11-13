"""Manage an isolated, real local stack for integration testing.

Uses only project-specific test volumes and a loopback port. Credentials below
belong exclusively to this disposable fixture, never to a deployed instance.
"""
import copy
import json
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".validation/local-stack"
META = STATE / "meta.json"


def prepare():
    if META.exists():
        raise SystemExit("Fixture already exists; use its up/status/down commands.")
    STATE.mkdir(parents=True, exist_ok=True)
    source = json.loads(subprocess.check_output(["docker", "compose", "-f", "docker-compose.dokploy.yml", "config", "--format", "json"], cwd=ROOT))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    project = "wand-local-check-" + uuid.uuid4().hex[:10]
    env = {"POSTGRES_USER": "postgres", "POSTGRES_PASSWORD": "local-fixture-password",
           "COMPOSE_PROJECT_NAME": project, "GAME_ADDRESS": "game.localhost", "GAME_LOGIN_PORT": "6112",
           "WEB_LEGACY_PLAY": f"http://old.localhost:{port}", "WEB_LEGACY_MEDIA": f"http://legacy.localhost:{port}",
           "WEB_VANILLA_PLAY": f"http://play.localhost:{port}", "WEB_VANILLA_MEDIA": f"http://media.localhost:{port}",
           "SNOWFLAKE_HOST": "snow.localhost", "SNOWFLAKE_PORT": "7002", "LEGACY_PLAYER": "ruffle", "VANILLA_PLAYER": "ruffle",
           "WEB_RECAPTCHA_SECRET": "", "WEB_RECAPTCHA_SITE": "", "WEB_HOSTNAME": "Wand Local Test",
           "EMAIL_METHOD": "", "EMAIL_FROM_ADDRESS": "fixture@example.invalid", "EMAIL_SENDGRID_KEY": "",
           "EMAIL_SMTP_HOST": "", "EMAIL_SMTP_PORT": "25", "EMAIL_SMTP_USER": "", "EMAIL_SMTP_PASS": "", "EMAIL_SMTP_SSL": "FALSE"}
    fixture = {"services": copy.deepcopy(source["services"]), "networks": {"wand": {}},
               "volumes": {name: {} for name in source["volumes"]}}
    for name in ("houdini", "dash", "snowflake"):
        shutil.copytree(ROOT / name, STATE / name, ignore=shutil.ignore_patterns(".git", "__pycache__", "logs", "*.log"))
    envfile = STATE / "fixture.env"
    envfile.write_text("\n".join(f"{key}={value}" for key, value in env.items()) + "\n")
    for name, service in fixture["services"].items():
        service.pop("labels", None)
        service.pop("restart", None)
        service.pop("ports", None)
        service["environment"] = dict(env)
        if name == "snowflake":
            service["environment"].update(POSTGRES_HOST="db", REDIS_HOST="redis", MEDIA_LOCATION=env["WEB_VANILLA_MEDIA"], PORT="7002")
        for mount in service.get("volumes", []):
            if mount["type"] == "bind":
                if mount["target"] in ("/usr/src/houdini", "/usr/src/dash", "/usr/src/snowflake"):
                    mount["source"] = str(STATE / mount["target"].rsplit("/", 1)[1])
                elif mount["target"] == "/usr/src/snowflake/.env":
                    mount["source"] = str(envfile)
                    mount["read_only"] = True
                else:
                    mount["read_only"] = True
        if name.startswith("houdini_"):
            command = service["command"]
            for option, value in (("--database-password", env["POSTGRES_PASSWORD"]), ("--database-user", "postgres"), ("--database-name", "postgres")):
                command[command.index(option) + 1] = value
            if name == "houdini_login":
                command[command.index("--port") + 1] = env["GAME_LOGIN_PORT"]
        if name == "web":
            service["ports"] = [{"target": 80, "published": str(port), "host_ip": "127.0.0.1", "protocol": "tcp"}]
            generated = STATE / "generated"
            generated.mkdir(exist_ok=True)
            english = generated / "vanilla-en"
            shutil.copytree(ROOT / "vanilla-media/play/en", english)
            # This destination does not exist in the pinned media checkout.
            # Give only that small subtree a writable fixture copy.
            (english / "index.html").touch()
            service["volumes"].append({"type": "bind", "source": str(english),
                "target": "/usr/share/nginx/vanilla/play/en", "bind": {"create_host_path": False}})
            # Only generated files are writable; original media stays read-only.
            for i, arg in enumerate(service["command"]):
                if i and service["command"][i - 1] == "-template":
                    destination = arg.split(":", 1)[1]
                    if destination.startswith("/usr/share/nginx/"):
                        file = generated / str(i)
                        file.touch()
                        service["volumes"].append({"type": "bind", "source": str(file), "target": destination,
                                                   "bind": {"create_host_path": False}})
    compose = STATE / "compose.json"
    compose.write_text(json.dumps(fixture, indent=2))
    META.write_text(json.dumps({"project": project, "port": port, "environment": env}, indent=2))
    print(f"Prepared {project} on loopback port {port}.")


def command(*args):
    meta = json.loads(META.read_text())
    return ["docker", "compose", "-p", meta["project"], "-f", str(STATE / "compose.json"), *args]


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "prepare":
        prepare()
    elif action == "up":
        subprocess.run(command("up", "-d", "--build", "--wait", "--wait-timeout", "300"), check=True)
    elif action == "status":
        subprocess.run(command("ps"), check=True)
    elif action == "down":
        # --volumes is confined to this randomly named, recorded fixture project.
        assert json.loads(META.read_text())["project"].startswith("wand-local-check-")
        subprocess.run(command("down", "--volumes", "--remove-orphans"), check=True)
    else:
        raise SystemExit("Use prepare, up, status or down")

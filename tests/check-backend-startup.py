"""Cold start and dependency recreation using real Houdini and temporary data.

No production volumes, ports, credentials or networks are used.
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

source = json.loads(subprocess.check_output(["docker", "compose", "config", "--format", "json"]))
houdini = ["houdini_login", "houdini_blizzard", "houdini_glaciar", "houdini_avalanche", "houdini_yeti"]
names = ["db", "redis", *houdini]
fixture = {"services": {name: copy.deepcopy(source["services"][name]) for name in names}}
for name, service in fixture["services"].items():
    service.pop("ports", None)
    service.pop("links", None)
    service.pop("labels", None)
    service.pop("restart", None)
    service["networks"] = {"default": {"aliases": [name]}}
    service["environment"] = {}
    if name in houdini:
        command = service["command"]
        command[command.index("--database-password") + 1] = "fixture-password"
        command[command.index("--database-user") + 1] = "postgres"
        command[command.index("--database-name") + 1] = "postgres"
    elif name == "db":
        service["environment"] = {"POSTGRES_USER": "postgres", "POSTGRES_PASSWORD": "fixture-password"}
        service["volumes"] = [mount for mount in service["volumes"] if mount["target"] == "/docker-entrypoint-initdb.d/houdini.sql"]
        service["tmpfs"] = ["/var/lib/postgresql/data"]
    elif name == "redis":
        service.pop("volumes", None)
        service["tmpfs"] = ["/data"]

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "compose.json"
    path.write_text(json.dumps(fixture))
    command = ["docker", "compose", "-p", "wand-startup-check-" + uuid.uuid4().hex[:10], "-f", str(path)]

    def up():
        subprocess.run([*command, "up", "-d", "--build", "--wait", "--wait-timeout", "180"], check=True)

    def started(service):
        container = subprocess.check_output([*command, "ps", "-q", service], text=True).strip()
        return subprocess.check_output(["docker", "inspect", "--format", "{{.State.StartedAt}}", container], text=True).strip()

    try:
        up()
        before = {name: started(name) for name in houdini}
        print("Cold start: login and four worlds healthy using the real protocol handshake.")
        # Mimic Compose replacing the database container during a deployment.
        # The fixture DB is deliberately ephemeral and initialized again.
        fixture["services"]["db"]["labels"] = {"wand.test.revision": "2"}
        path.write_text(json.dumps(fixture))
        up()
        for name in houdini:
            assert started(name) != before[name], f"{name} was not restarted after the database changed"
        print("Database recreation: login and all four worlds automatically restarted and became healthy.")
        subprocess.run([*command, "stop", *houdini[1:]], check=True)
        up()
        print("A single Compose up started all four stopped worlds; no individual restarts required.")
    except BaseException:
        subprocess.run([*command, "logs", "--tail", "80"], check=False)
        raise
    finally:
        subprocess.run([*command, "down"], check=False)

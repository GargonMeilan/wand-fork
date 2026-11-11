"""Verify DB/Redis data survives force-recreate, using new disposable test volumes.

Production mount paths and volume names are never used. Cleanup is confined to
the unique fixture project and the two volumes created by this test.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

source = json.loads(subprocess.check_output(["docker", "compose", "config", "--format", "json"]))
for service, target, key in (("db", "/var/lib/postgresql/data", "postgres_data"), ("redis", "/data", "redis_data")):
    mount = next(m for m in source["services"][service]["volumes"] if m["target"] == target)
    assert mount["type"] == "volume" and mount["source"] == key, mount

project = "wand-persistence-check-" + uuid.uuid4().hex[:10]
fixture = {"services": {}, "volumes": {"postgres_data": {"name": project + "-postgres"}, "redis_data": {"name": project + "-redis"}}}
for name, target, volume in (("db", "/var/lib/postgresql/data", "postgres_data"), ("redis", "/data", "redis_data")):
    original = source["services"][name]
    service = {key: original[key] for key in ("image", "healthcheck")}
    if "command" in original:
        service["command"] = original["command"]
    service["volumes"] = [{"type": "volume", "source": volume, "target": target}]
    if name == "db":
        service["environment"] = {"POSTGRES_USER": "postgres", "POSTGRES_PASSWORD": "fixture-password"}
    fixture["services"][name] = service

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "compose.json"
    path.write_text(json.dumps(fixture))
    command = ["docker", "compose", "-p", project, "-f", str(path)]

    def run(*args):
        return subprocess.check_output([*command, *args], text=True).strip()

    def query(sql):
        return run("exec", "-T", "db", "psql", "-U", "postgres", "-At", "-c", sql)

    try:
        run("up", "-d", "--wait", "--wait-timeout", "60")
        query("CREATE TABLE persistence_probe (value text); INSERT INTO persistence_probe VALUES ('survives-redeploy');")
        run("exec", "-T", "redis", "redis-cli", "SET", "persistence_probe", "survives-redeploy")
        run("exec", "-T", "redis", "redis-cli", "SAVE")
        run("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "60")
        assert query("SELECT value FROM persistence_probe") == "survives-redeploy"
        assert run("exec", "-T", "redis", "redis-cli", "--raw", "GET", "persistence_probe") == "survives-redeploy"
        print("PostgreSQL row and Redis key survived container recreation in Docker volumes.")
    except BaseException:
        subprocess.run([*command, "logs"], check=False)
        raise
    finally:
        # Only remove the two uniquely named fixture volumes declared above.
        subprocess.run([*command, "down", "--volumes"], check=False)

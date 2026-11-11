"""Run only the configured Redis image/command/healthcheck with temporary data."""
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

config = json.loads(subprocess.check_output(["docker", "compose", "config", "--format", "json"]))
redis = config["services"]["redis"]
assert redis["healthcheck"]["test"] == ["CMD", "redis-cli", "ping"]
# Deliberately omit all production mounts, ports, networks and other services.
isolated = {"services": {"redis": {key: redis[key] for key in ("image", "command", "healthcheck")}}}
isolated["services"]["redis"]["tmpfs"] = ["/data"]
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "compose.json"
    path.write_text(json.dumps(isolated))
    command = ["docker", "compose", "-p", "wand-redis-check-" + uuid.uuid4().hex[:10], "-f", str(path)]
    try:
        subprocess.run([*command, "up", "-d", "--wait", "--wait-timeout", "45"], check=True)
        subprocess.run([*command, "exec", "-T", "redis", "redis-cli", "ping"], check=True)
        print("Redis became healthy using the production exec healthcheck and temporary in-memory data.")
    except BaseException:
        subprocess.run([*command, "logs"], check=False)
        raise
    finally:
        subprocess.run([*command, "down"], check=False)

"""Missing source mounts must not recreate directories inside a Git checkout."""
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

import yaml

raw = yaml.safe_load(Path("docker-compose.yml").read_text())
for service, configuration in raw["services"].items():
    for mount in configuration.get("volumes", []):
        if isinstance(mount, str):
            assert not mount.startswith("./"), (service, mount)
        elif mount.get("type") == "bind":
            assert mount.get("bind", {}).get("create_host_path") is False, (service, mount)

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    checkout = root / "checkout"
    upstream = root / "upstream"
    fixture = {"services": {"probe": {
        "image": raw["services"]["redis"]["image"],
        "entrypoint": ["sh", "-c", "exec sleep 600"],
        "volumes": [{"type": "bind", "source": str(checkout), "target": "/fixture",
                     "bind": {"create_host_path": False}}],
    }}}
    path = root / "compose.json"
    path.write_text(json.dumps(fixture))
    command = ["docker", "compose", "-p", "wand-bind-check-" + uuid.uuid4().hex[:10], "-f", str(path)]
    try:
        failed = subprocess.run([*command, "up", "-d"], capture_output=True, text=True)
        assert failed.returncode != 0, "Docker unexpectedly started with an absent bind source"
        assert "bind source path does not exist" in failed.stderr, failed.stderr
        assert not checkout.exists(), "Docker recreated the checkout directory before Git could clone"
        print("Missing source rejected without creating a checkout directory.")
        subprocess.run(["git", "init", "-q", str(upstream)], check=True)
        (upstream / "asset.txt").write_text("original-git-asset")
        subprocess.run(["git", "-C", str(upstream), "add", "asset.txt"], check=True)
        subprocess.run(["git", "-C", str(upstream), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "fixture"], check=True)
        subprocess.run(["git", "clone", "-q", str(upstream), str(checkout)], check=True)
        subprocess.run([*command, "up", "-d"], check=True)
        asset = subprocess.check_output([*command, "exec", "-T", "probe", "cat", "/fixture/asset.txt"], text=True)
        assert asset == "original-git-asset"
        print("Git cloned into the untouched destination and the container mounted its original asset.")
    finally:
        subprocess.run([*command, "down"], check=False)

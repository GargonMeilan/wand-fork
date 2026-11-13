"""Verify or restore the pinned, preinstalled historical event catalogue.

The manifest is the lockfile: no moving branch, downloaded code or user uploads
are needed. Normal application startup performs no network requests.
"""
import argparse
import concurrent.futures
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from world_manager.store import validate_swf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", action="store_true", help="Download missing or corrupt assets from their pinned source URLs")
    parser.add_argument("--verify", action="store_true", help="Verify local files (the default)")
    args = parser.parse_args()
    directory = ROOT / "world_manager/catalog"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    prefix = "https://raw.githubusercontent.com/nhaar/Waddle-Forever/" + manifest["upstream_commit"] + "/media/default/archives/"
    assets = {item["sha256"]: item for event in manifest["events"] for item in event["rooms"] + event["resources"]}

    def check(pair):
        digest, item = pair
        path = directory / "assets" / (digest + ".swf")
        body = path.read_bytes() if path.is_file() else b""
        if hashlib.sha256(body).hexdigest() != digest and args.repair:
            if not item["url"].startswith(prefix):
                raise ValueError("Asset URL is outside the pinned archive")
            with urllib.request.urlopen(item["url"], timeout=30) as response:
                body = response.read(16 * 1024 * 1024 + 1)
            if hashlib.sha256(body).hexdigest() != digest:
                raise ValueError("Downloaded asset hash does not match the catalogue")
            validate_swf(body)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        if len(body) != item["size"] or hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("Missing or corrupt asset: " + digest + "; run with --repair")
        validate_swf(body)
        git_hash = hashlib.sha1(b"blob " + str(len(body)).encode() + bytes([0]) + body).hexdigest()
        if git_hash != item["git_blob"]:
            raise ValueError("Git blob hash does not match the pinned source")
        return len(body)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        sizes = list(executor.map(check, assets.items()))
    print("{} events, {} room variants, {} companion references; {} unique files verified ({:.1f} MiB).".format(
        len(manifest["events"]), sum(len(e["rooms"]) for e in manifest["events"]),
        sum(len(e["resources"]) for e in manifest["events"]), len(assets), sum(sizes) / 1024**2))


if __name__ == "__main__":
    main()

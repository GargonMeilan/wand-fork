"""Add expiring presence snapshots without editing Houdini's submodule."""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if __name__ == "__main__":
    from houdini.houdini import Houdini
    from world_manager.presence import install

    install(Houdini)
    runpy.run_path("bootstrap.py", run_name="__main__")

"""Register Wand extensions, then run Dash's original CLI."""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from world_manager.routes import install

if __name__ == "__main__":
    install()
    runpy.run_path("bootstrap.py", run_name="__main__")

"""Generate the steady synthetic EQ listening aid without playing audio."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecc3852.demo import ensure_listening_demo

if __name__ == "__main__":
    print(ensure_listening_demo())

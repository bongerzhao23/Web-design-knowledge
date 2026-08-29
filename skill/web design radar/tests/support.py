import sys
from pathlib import Path


def import_package() -> None:
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))

"""Make the tests directory importable so the py adapter can load the
sample guard functions by module name."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

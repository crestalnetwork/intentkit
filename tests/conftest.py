import os
import sys
from pathlib import Path

os.environ.setdefault("REDIS_HOST", "localhost")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

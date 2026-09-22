"""Vercel entrypoint. The filesystem is read-only except /tmp, so reports are not saved and the legalize cache goes to /tmp."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("LEGALIZE_CACHE_DIR", "/tmp/legalize-cache")

from legal_verify.web import create_app  # noqa: E402

app = create_app(save_dir=None)

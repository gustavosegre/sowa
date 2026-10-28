"""Write the OpenAPI schema to a file (used by `make types`)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> None:
    # Importing the app must not touch the real data directory.
    os.environ.setdefault("FORJA_DATA_DIR", tempfile.mkdtemp(prefix="forja-openapi-"))
    from forja.main import app

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OpenAPI -> {out}")


if __name__ == "__main__":
    main()

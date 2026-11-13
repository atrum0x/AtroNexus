"""Write the OpenAPI spec to a file without starting the server.

    uv run python -m app.export_openapi ../frontend/openapi.json

The frontend's `npm run gen:api` runs this, then Orval.
"""

import json
import os
import sys
from pathlib import Path

# Settings need a secret to load, but the spec doesn't depend on its value.
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("ENCRYPTION_KEY", "x" * 44)

from app.main import app  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()

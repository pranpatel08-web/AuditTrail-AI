"""Start AuditTrail AI with one command.

    python run.py                # http://127.0.0.1:8000
    python run.py --port 8080
    python run.py --reload       # development

Works from a fresh clone with `pip install -r requirements.txt`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AuditTrail AI server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    if args.reload:
        uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=True, reload_dirs=[str(ROOT)])
    else:
        from backend.main import app

        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

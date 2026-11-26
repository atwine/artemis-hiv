"""Run the backend:  python -m backend   (listens on 127.0.0.1:8000 unless .env says otherwise)."""

from __future__ import annotations

import uvicorn
from dotenv import load_dotenv

from backend.settings import settings_from_env


def main() -> None:
    load_dotenv()
    s = settings_from_env()
    uvicorn.run("backend.main:create_app", factory=True, host=s.host, port=s.port)


if __name__ == "__main__":
    main()

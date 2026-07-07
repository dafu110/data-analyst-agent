from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    sys.stderr.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

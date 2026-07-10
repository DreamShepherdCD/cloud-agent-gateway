"""Read OAuth credentials from persistent oauth.json.

Panel environment variables may contain stale values (they are not
updated when the OAuth application is recreated).  Always prefer the
persistent file which is the setup page's source of truth.

Tries all well-known paths; falls back to environment variables only
as a last resort (HF ``hf_oauth:true`` auto-injection).
"""

import json
import os
from typing import Tuple

_PATHS = [
    "/mnt/workspace/instances/default/oauth.json",
    "/mnt/workspace/oauth.json",
    "/data/instances/default/oauth.json",
    "/data/oauth.json",
]


def read_oauth_json() -> Tuple[str, str]:
    for path in _PATHS:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                cid = data.get("client_id") or data.get("app_id") or ""
                secret = data.get("client_secret") or data.get("app_secret") or ""
                if cid and secret:
                    return cid, secret
            except Exception:
                continue
    return os.environ.get("OAUTH_CLIENT_ID", ""), os.environ.get("OAUTH_CLIENT_SECRET", "")

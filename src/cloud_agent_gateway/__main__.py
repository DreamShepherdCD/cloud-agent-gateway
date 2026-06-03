"""cloud-agent-gateway entry point.

Usage::

    python -m cloud_agent_gateway [--port 7860] [--agent nanobot]

Environment variables:
    NANOBOT_WS_PORT   — agent WebSocket port (default: 7870)
    NANOBOT_GW_PORT   — agent gateway port (default: 17860)
    OAUTH_PROXY_PORT  — proxy listen port (default: 7860)
"""

import os
import sys

from cloud_agent_gateway.oauth_proxy import main

if __name__ == "__main__":
    main()

# cloud-agent-gateway

Framework-agnostic cloud deployment layer for AI agents — pip-installable sidecar.

## Overview

`cloud-agent-gateway` provides a unified platform abstraction for deploying AI agents on cloud platforms (HuggingFace Spaces, ModelScope Studio, etc.) with graceful degradation and capability detection.

## Platforms

| Platform | Class | OAuth | Squad Relay | Notes |
|----------|-------|-------|-------------|-------|
| HF Staging | `HFStagingPlatform` | ✅ | ✅ | Full OAuth + WS identity injection |
| HF Direct | `HFDirectPlatform` | — | ✅ | Squad relay only, no OAuth |
| HF Spaces | `HFSpacesPlatform` | ✅ | ✅ | HF OAuth via authlib |
| ModelScope | `ModelScopePlatform` | ✅ | ✅ | MS OAuth + route bypass |
| ModelScope Squad | `ModelScopeSquadPlatform` | ✅ | ✅ | Internal squad variant |

## Install

```bash
pip install cloud-agent-gateway
```

## Usage

```python
from cloud_agent_gateway.platforms import platform

# Platform auto-detected from DEPLOY_PLATFORM env var
print(platform.PLATFORM_NAME)

# Check capabilities
if platform.can_oauth:
    # Platform supports OAuth identity resolution
    ...

if platform.is_hf:
    # HuggingFace-specific behavior
    ...
```

## License

MIT

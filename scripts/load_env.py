#!/usr/bin/env python3
"""
Load project environment variables script
Get project environment variables via coze_workload_identity.Client and output export statements
Usage: eval $(python load_env.py)
"""

import os
import sys

# Add app directory to Python path
workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
app_dir = os.path.join(workspace_path, 'src')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

try:
    from coze_workload_identity import Client

    client = Client()
    env_vars = client.get_project_env_vars()
    client.close()

    # Output environment variables in export statement format
    for env_var in env_vars:
        # Escape special characters
        value = env_var.value.replace("'", "'\\''")
        print(f"export {env_var.key}='{value}'")

    # Output success message to stderr, does not affect eval
    print(f"# Successfully loaded {len(env_vars)} environment variables", file=sys.stderr)

except Exception as e:
    print(f"# Error loading environment variables: {e}", file=sys.stderr)
    sys.exit(1)

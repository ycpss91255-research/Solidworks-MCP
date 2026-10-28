#!/usr/bin/env python3
"""Crash-isolating entry point: runs solidworks_mcp_server.py as a child process
and restarts it (replaying the MCP handshake) if it dies. See
solidworks_mcp/supervisor.py. Use this file instead of solidworks_mcp_server.py
in the MCP client configuration."""

import os
import sys

package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

from solidworks_mcp.supervisor import main

if __name__ == "__main__":
    sys.exit(main())

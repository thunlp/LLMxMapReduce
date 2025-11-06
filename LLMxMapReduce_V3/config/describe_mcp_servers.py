#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility script to inspect user-defined MCP server entries in config/unified_config.json.
"""

import json
from pathlib import Path
from textwrap import indent

CONFIG_PATH = Path(__file__).resolve().parent / "unified_config.json"


def format_env(env: dict) -> str:
    if not env:
        return "    (none)"
    lines = [f"{key}={value}" for key, value in env.items()]
    return indent("\n".join(lines), "    ")


def describe_servers(servers):
    if not servers:
        print("No additional MCP servers configured.")
        return

    for idx, server in enumerate(servers, 1):
        name = server.get("name", f"server_{idx}")
        command = server.get("command", "(not specified)")
        args = server.get("args", [])
        cwd = server.get("cwd")
        env = server.get("env", {})

        print(f"[Server {idx}] {name}")
        print(f"  command: {command}")
        print(f"  args   : {args}")
        print(f"  cwd    : {cwd or '(none)'}")
        print("  env    :")
        print(format_env(env))
        print("")


def main():
    if not CONFIG_PATH.exists():
        print(f"Config file not found: {CONFIG_PATH}")
        return

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Failed to parse config: {exc}")
        return

    servers = config.get("additional_mcp_servers", [])
    describe_servers(servers)


if __name__ == "__main__":
    main()


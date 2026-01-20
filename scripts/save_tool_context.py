#!/usr/bin/env python3
"""Save tool context for Telegram notifications.

PreToolUse hook: Saves tool information to a temp file
so that Notification hook can include detailed command info.

Claude Code PreToolUse hook input:
{
  "session_id": "string",
  "tool_name": "Bash",
  "tool_input": {
    "command": "git push origin main",
    "description": "Push commits to remote"
  },
  ...
}
"""

import sys
import os
import json

CONTEXT_FILE = "/tmp/claude_tool_context.json"


def read_stdin_json() -> dict:
    """Read JSON from stdin (Claude Code hook input)."""
    try:
        # Check if stdin has data (with longer timeout for reliability)
        if not sys.stdin.isatty():
            stdin_data = sys.stdin.read()
            if stdin_data.strip():
                return json.loads(stdin_data)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse stdin JSON: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Failed to read stdin: {e}", file=sys.stderr)
    return {}


def save_tool_context(hook_data: dict) -> None:
    """Save tool context to temp file."""
    tool_name = hook_data.get("tool_name", "")
    tool_input = hook_data.get("tool_input", {})
    session_id = hook_data.get("session_id", "")

    context = {
        "session_id": session_id,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": os.getcwd(),
    }

    try:
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(context, f, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to save tool context: {e}", file=sys.stderr)


if __name__ == "__main__":
    hook_data = read_stdin_json()

    if hook_data:
        save_tool_context(hook_data)

    # Always exit 0 to not block tool execution
    sys.exit(0)

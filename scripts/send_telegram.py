#!/usr/bin/env python3
"""Send Telegram notification via Bot API.

Claude Code Notification hooks receive JSON via stdin:
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "hook_event_name": "Notification",
  "message": "The actual notification message",
  "notification_type": "permission_prompt | idle_prompt | ..."
}
"""

import os
import sys
import re
import urllib.request
import urllib.parse
import json
import select

# Notification type to Korean title mapping
NOTIFICATION_TITLES = {
    "permission_prompt": "🔐 권한 요청",
    "idle_prompt": "⏳ 입력 대기",
    "auth_success": "✅ 인증 성공",
    "elicitation_dialog": "💬 추가 정보 필요",
}

TOOL_CONTEXT_FILE = "/tmp/claude_tool_context.json"


def send_telegram(title: str, message: str, preformatted: bool = False) -> bool:
    """Send a message to Telegram.

    Args:
        title: Notification title
        message: Notification message
        preformatted: If True, message contains markdown and shouldn't be escaped
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return False

    # Handle empty values
    title = title.strip() if title else "알림"
    message = message.strip() if message else "Claude Code 이벤트 발생"

    # Escape only necessary Markdown v1 special characters
    # Telegram Markdown v1 only needs: _ * ` [
    def escape_markdown(text: str) -> str:
        for char in ['_', '*', '`', '[']:
            text = text.replace(char, f'\\{char}')
        return text

    # Only escape if not preformatted
    final_message = message if preformatted else escape_markdown(message)

    # Format message with separator lines
    separator = "─" * 20
    text = f"🔔 *Claude Code Notify*\n\n*{title}*\n{separator}\n{final_message}\n{separator}"

    # Prepare API request
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("ok"):
                print("Notification sent successfully")
                return True
            else:
                print(f"API error: {result}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"Failed to send notification: {e}", file=sys.stderr)
        return False


def read_stdin_json() -> dict:
    """Read JSON from stdin (Claude Code hook input)."""
    # Check if there's data on stdin (non-blocking)
    if select.select([sys.stdin], [], [], 0.1)[0]:
        try:
            stdin_data = sys.stdin.read()
            if stdin_data.strip():
                return json.loads(stdin_data)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse stdin JSON: {e}", file=sys.stderr)
    return {}


def debug_hook_input(hook_data: dict):
    """Debug: Print hook input data."""
    print("=== Debug: Hook Input ===", file=sys.stderr)
    print(json.dumps(hook_data, indent=2, ensure_ascii=False), file=sys.stderr)
    print("=========================", file=sys.stderr)

    # Also save to file for later inspection
    debug_file = "/tmp/telegram_hook_debug.json"
    try:
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(hook_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def read_tool_context() -> dict:
    """Read tool context saved by PreToolUse hook."""
    try:
        if os.path.exists(TOOL_CONTEXT_FILE):
            with open(TOOL_CONTEXT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to read tool context: {e}", file=sys.stderr)
    return {}


def read_last_assistant_message(transcript_path: str, max_lines: int = 50) -> str:
    """Read Claude's last output from transcript file.

    Extracts the last assistant message to show what Claude asked/said
    before waiting for user input.

    Args:
        transcript_path: Path to the transcript JSONL file
        max_lines: Maximum number of lines to include in the summary

    Returns:
        Summarized last assistant message, or empty string if not found
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return ""

    try:
        last_assistant_content = ""

        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Look for assistant messages
                    if entry.get("type") == "assistant":
                        message = entry.get("message", {})
                        content = message.get("content", [])

                        # Extract text content from the message
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif isinstance(item, str):
                                text_parts.append(item)

                        if text_parts:
                            last_assistant_content = "\n".join(text_parts)
                except json.JSONDecodeError:
                    continue

        if not last_assistant_content:
            return ""

        # Summarize the content: take first and last parts if too long
        lines = last_assistant_content.strip().split("\n")

        # Filter out empty lines and very short lines
        lines = [l for l in lines if l.strip()]

        if len(lines) <= max_lines:
            # Short enough, return as-is (truncate individual lines if needed)
            result_lines = []
            for line in lines:
                if len(line) > 100:
                    result_lines.append(line[:100] + "...")
                else:
                    result_lines.append(line)
            return "\n".join(result_lines)

        # Too long: take first few lines, ellipsis, last few lines
        head_lines = 5
        tail_lines = 10

        result = []
        for line in lines[:head_lines]:
            if len(line) > 100:
                result.append(line[:100] + "...")
            else:
                result.append(line)

        result.append("...")

        for line in lines[-tail_lines:]:
            if len(line) > 100:
                result.append(line[:100] + "...")
            else:
                result.append(line)

        return "\n".join(result)

    except Exception as e:
        print(f"Warning: Failed to read transcript: {e}", file=sys.stderr)
        return ""


def read_skill_description(skill_name: str) -> str:
    """Read skill description from SKILL.md file.

    Searches in common skill locations:
    - ~/.claude/skills/<skill-name>/SKILL.md
    - ~/.claude/plugins/cache/<org>/<plugin>/<version>/skills/<skill-name>/SKILL.md
    """
    skill_dirs = [
        os.path.expanduser(f"~/.claude/skills/{skill_name}"),
    ]

    # If skill name contains ':', it might be a plugin skill like "superpowers:brainstorming"
    if ':' in skill_name:
        plugin, skill = skill_name.split(':', 1)
        skill_dirs.insert(0, os.path.expanduser(f"~/.claude/skills/{plugin}"))

        # Search plugins cache: ~/.claude/plugins/cache/<org>/<plugin>/<version>/skills/<skill>/
        plugins_cache = os.path.expanduser("~/.claude/plugins/cache")
        if os.path.exists(plugins_cache):
            for org_dir in os.listdir(plugins_cache):
                org_path = os.path.join(plugins_cache, org_dir)
                if not os.path.isdir(org_path):
                    continue
                for plugin_dir in os.listdir(org_path):
                    if plugin in plugin_dir:
                        plugin_path = os.path.join(org_path, plugin_dir)
                        if not os.path.isdir(plugin_path):
                            continue
                        # Find version directories
                        for version_dir in os.listdir(plugin_path):
                            skills_path = os.path.join(plugin_path, version_dir, "skills", skill)
                            if os.path.isdir(skills_path):
                                skill_dirs.append(skills_path)

    for skill_dir in skill_dirs:
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if os.path.exists(skill_md):
            try:
                with open(skill_md, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Extract description from frontmatter
                    frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
                    if frontmatter_match:
                        frontmatter = frontmatter_match.group(1)
                        desc_match = re.search(r'description:\s*(.+?)(?:\n[a-z]|\n---|\Z)', frontmatter, re.DOTALL)
                        if desc_match:
                            return desc_match.group(1).strip()
            except Exception:
                pass

    return ""


def format_tool_info(tool_context: dict) -> str:
    """Format tool information for notification message.

    Format:
    command or action
    description

    Do you want to proceed?
    """
    tool_name = tool_context.get("tool_name", "")
    tool_input = tool_context.get("tool_input", {})

    if not tool_name:
        return ""

    parts = []

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        description = tool_input.get("description", "")
        if command:
            # Truncate long commands
            if len(command) > 200:
                command = command[:200] + "..."
            parts.append(f"```\n{command}\n```")
        if description:
            parts.append(f"_{description}_")
    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
        if file_path:
            parts.append(f"```\nEdit: {file_path}\n```")
    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        if file_path:
            parts.append(f"```\nWrite: {file_path}\n```")
    elif tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if file_path:
            parts.append(f"```\nRead: {file_path}\n```")
    elif tool_name == "AskUserQuestion":
        # Show actual question text
        questions = tool_input.get("questions", [])
        if questions:
            q_texts = []
            for q in questions:
                question_text = q.get("question", "")
                header = q.get("header", "")
                if question_text:
                    prefix = f"[{header}] " if header else ""
                    q_texts.append(f"{prefix}{question_text}")
            if q_texts:
                parts.append("```\n" + "\n".join(q_texts) + "\n```")
    elif tool_name == "Skill":
        # Show skill name, description, and standard prompt
        skill_name = tool_input.get("skill", "")
        args = tool_input.get("args", "")
        if skill_name:
            parts.append(f"*Use skill \"{skill_name}\"?*")
            parts.append("_Claude may use instructions, code, or files from this Skill._\n")

            # Try to read skill description from SKILL.md
            description = read_skill_description(skill_name)
            if description:
                # Truncate if too long
                if len(description) > 300:
                    description = description[:300] + "..."
                parts.append(f"{description}\n")

            if args:
                parts.append(f"_args: {args}_\n")

            # Get cwd from tool context for option 2
            cwd = tool_context.get("cwd", "")
            cwd_short = os.path.basename(cwd) if cwd else ""

            parts.append("*Do you want to proceed?*")
            parts.append("1. Yes")
            if cwd_short:
                parts.append(f"2. Yes, and don't ask again for {skill_name} in {cwd_short}")
            else:
                parts.append(f"2. Yes, and don't ask again for {skill_name}")
            parts.append("3. No")
    else:
        # For other tools, show tool name and params
        parts.append(f"```\n{tool_name}\n```")
        if tool_input:
            summary = ", ".join(f"{k}" for k in list(tool_input.keys())[:3])
            parts.append(f"_params: {summary}_")

    return "\n".join(parts)


if __name__ == "__main__":
    # Check if notifications are enabled (default: true)
    if os.environ.get("CLAUDE_TELEGRAM_NOTIFY_ENABLED", "true").lower() == "false":
        sys.exit(0)

    debug = os.environ.get("CLAUDE_TELEGRAM_DEBUG")

    preformatted = False

    # Priority 1: Command line arguments
    if len(sys.argv) >= 3:
        title = sys.argv[1]
        message = sys.argv[2]
    else:
        # Priority 2: Read from stdin (Claude Code hook JSON)
        hook_data = read_stdin_json()

        # Skip permission_prompt - handled by telegram-dialog/permission_handler.py
        if hook_data.get("notification_type") == "permission_prompt":
            sys.exit(0)

        if debug:
            debug_hook_input(hook_data)
            # Send debug info to Telegram
            debug_msg = f"Hook data keys: {list(hook_data.keys())}\n\n"
            debug_msg += f"Full data:\n{json.dumps(hook_data, indent=2, ensure_ascii=False)[:500]}"
            send_telegram("🔧 DEBUG", debug_msg)

        if hook_data:
            # Extract notification type and message from hook JSON
            notification_type = hook_data.get("notification_type", "")
            raw_message = hook_data.get("message", "")

            # Get Korean title based on notification type
            title = NOTIFICATION_TITLES.get(notification_type, f"📢 {notification_type or '알림'}")

            # For permission_prompt, include tool context info + options
            preformatted = False
            if notification_type == "permission_prompt":
                tool_context = read_tool_context()
                tool_info = format_tool_info(tool_context)

                # Build options text dynamically from tool context
                options_text = "\n\nDo you want to proceed?\n1. Yes\n"

                # Generate "don't ask again" option from tool context
                if tool_context:
                    tool_input = tool_context.get("tool_input", {})
                    cmd = tool_input.get("command", "")
                    cwd = tool_context.get("cwd", "")

                    # Extract short command (first part before pipe/redirect)
                    short_cmd = cmd.split("|")[0].split(">")[0].split("2>&1")[0].strip()
                    if len(short_cmd) > 50:
                        short_cmd = short_cmd[:50] + "..."

                    if short_cmd and cwd:
                        options_text += f"2. Yes, and don't ask again for `{short_cmd}` in {cwd}\n"
                    else:
                        options_text += "2. Yes, and don't ask again\n"
                else:
                    options_text += "2. Yes, and don't ask again\n"

                options_text += "3. No\n"

                if tool_info:
                    message = tool_info + options_text
                    preformatted = True
                else:
                    message = (raw_message or "") + options_text
            elif notification_type == "idle_prompt":
                # For idle_prompt, show Claude's last output (the question asked)
                transcript_path = hook_data.get("transcript_path", "")
                last_output = read_last_assistant_message(transcript_path)
                if last_output:
                    message = last_output
                else:
                    message = raw_message or "Claude is waiting for your input"
            else:
                message = raw_message
        else:
            # Fallback: Environment variables (legacy support)
            title = os.environ.get("CLAUDE_NOTIFICATION_TITLE", "")
            message = os.environ.get("CLAUDE_NOTIFICATION_MESSAGE", "")

    success = send_telegram(title, message, preformatted=preformatted)
    sys.exit(0 if success else 1)

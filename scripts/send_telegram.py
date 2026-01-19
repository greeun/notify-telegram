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


def send_telegram(title: str, message: str) -> bool:
    """Send a message to Telegram."""
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

    escaped_message = escape_markdown(message)

    # Format message
    text = f"🤖 *Claude Code*\n\n*{title}*\n\n{escaped_message}"

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


if __name__ == "__main__":
    # Check if notifications are enabled (default: true)
    if os.environ.get("CLAUDE_TELEGRAM_NOTIFY_ENABLED", "true").lower() == "false":
        sys.exit(0)

    debug = os.environ.get("TELEGRAM_DEBUG")

    # Priority 1: Command line arguments
    if len(sys.argv) >= 3:
        title = sys.argv[1]
        message = sys.argv[2]
    else:
        # Priority 2: Read from stdin (Claude Code hook JSON)
        hook_data = read_stdin_json()

        if debug:
            debug_hook_input(hook_data)

        if hook_data:
            # Extract notification type and message from hook JSON
            notification_type = hook_data.get("notification_type", "")
            raw_message = hook_data.get("message", "")

            # Get Korean title based on notification type
            title = NOTIFICATION_TITLES.get(notification_type, f"📢 {notification_type or '알림'}")
            message = raw_message
        else:
            # Fallback: Environment variables (legacy support)
            title = os.environ.get("CLAUDE_NOTIFICATION_TITLE", "")
            message = os.environ.get("CLAUDE_NOTIFICATION_MESSAGE", "")

    success = send_telegram(title, message)
    sys.exit(0 if success else 1)

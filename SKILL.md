---
name: telegram-notifier
description: Send Telegram notifications when tasks completed. Use when setting up notifications, configuring telegram alerts, or when user says "telegram notify", "send telegram", "notify me".
version: 1.1.0
---

# Telegram Notifier

Claude Code 작업 완료 또는 사용자 입력 필요 시 텔레그램으로 알림을 보냅니다.

## Quick Start

### 1. 환경 변수 설정

```bash
# ~/.zshrc 또는 ~/.bashrc에 추가
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

> 비활성화: `export CLAUDE_TELEGRAM_NOTIFY_ENABLED=false`

봇 토큰/채팅 ID가 없다면: [references/setup-guide.md](references/setup-guide.md) 참조

### 2. Claude Code Hooks 설정

`~/.claude/settings.json`에 추가:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/telegram-notifier/scripts/save_tool_context.py"
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/telegram-notifier/scripts/send_telegram.py"
          }
        ]
      }
    ]
  }
}
```

> **참고**:
> - `PreToolUse`: 도구 실행 전 컨텍스트(명령어, 파일 등) 저장
> - `Notification`: 저장된 컨텍스트 + 선택지 포함하여 알림 발송

## 알림 유형

| 유형 | 제목 | 설명 |
|------|------|------|
| `permission_prompt` | 🔐 권한 요청 | **이 스킬은 처리하지 않고 건너뜀** (아래 참고) |
| `idle_prompt` | ⏳ 입력 대기 | 사용자 응답 대기 중 |
| `auth_success` | ✅ 인증 성공 | 인증 완료 |
| `elicitation_dialog` | 💬 추가 정보 필요 | 추가 입력 필요 |

> **참고**: `permission_prompt`(권한 요청)는 텔레그램에서 승인/거부를 되돌려받는 양방향 흐름이 필요합니다. 이 스킬은 단방향 알림만 다루므로 해당 유형을 수신하면 즉시 종료합니다 — 사용자가 조작할 수 없는 알림을 보내지 않기 위해서입니다.

## 수동 알림 테스트

```bash
python3 ~/.claude/skills/telegram-notifier/scripts/send_telegram.py "테스트" "메시지 내용"
```

## Troubleshooting

| 문제 | 해결 |
|-----|-----|
| 알림 안 옴 | `echo $TELEGRAM_BOT_TOKEN` 확인 |
| 권한 오류 | 봇이 채팅방에 추가되었는지 확인 |
| Hook 미작동 | `~/.claude/settings.json` 문법 확인 |
| 디버그 모드 | `export TELEGRAM_DEBUG=1` 설정 후 확인 |

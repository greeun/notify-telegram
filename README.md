# Telegram Notifier for Claude Code

Claude Code 작업 완료 또는 사용자 입력 대기 시 텔레그램으로 자동 알림을 보내는 스킬입니다.

## 설치

### 1. 텔레그램 봇 생성

1. Telegram에서 **@BotFather** 검색
2. `/newbot` 명령 입력
3. 봇 이름 입력 (예: "Claude Notifier")
4. 봇 사용자명 입력 (`_bot`으로 끝나야 함)
5. 발급된 **Bot Token** 복사

### 2. Chat ID 확인

1. 생성한 봇에게 아무 메시지 발송
2. 브라우저에서 접속:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
3. JSON 응답에서 `"chat":{"id":123456789}` 부분의 숫자가 Chat ID

### 3. 환경 변수 설정

`~/.zshrc` 또는 `~/.bashrc`에 추가:

```bash
export CLAUDE_TELEGRAM_NOTIFY_ENABLED="1"
export TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
export TELEGRAM_CHAT_ID="123456789"
```

적용:
```bash
source ~/.zshrc
```

### 4. Claude Code Hooks 설정

`~/.claude/settings.json`에 hooks 추가:

```json
{
  "hooks": {
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

> **참고**: Claude Code는 알림 정보를 stdin을 통해 JSON으로 전달합니다. 커맨드 라인 인자는 필요하지 않습니다.

## 사용법

### 자동 알림

설정 완료 후 Claude Code가 다음 상황에서 자동으로 텔레그램 알림을 발송합니다:

| 알림 유형 | 제목 | 설명 |
|-----------|------|------|
| `permission_prompt` | 🔐 권한 요청 | 명령어 실행 권한 요청 (예: git push) |
| `idle_prompt` | ⏳ 입력 대기 | 60초 이상 사용자 응답 대기 |
| `auth_success` | ✅ 인증 성공 | 인증 완료 알림 |
| `elicitation_dialog` | 💬 추가 정보 필요 | MCP 도구가 추가 입력 요청 |

예시 알림 메시지:
```
🤖 *Claude Code*

*🔐 권한 요청*

git push - Push current branch to remote
Do you want to proceed?
```

### 수동 알림 테스트

```bash
python3 ~/.claude/skills/telegram-notifier/scripts/send_telegram.py "제목" "메시지 내용"
```

## 파일 구조

```
~/.claude/skills/telegram-notifier/
├── SKILL.md                    # 스킬 정의
├── README.md                   # 이 문서
├── scripts/
│   └── send_telegram.py        # 텔레그램 발송 스크립트
└── references/
    └── setup-guide.md          # 상세 설정 가이드
```

## 문제 해결

| 문제 | 해결 방법 |
|------|----------|
| 알림이 오지 않음 | `echo $TELEGRAM_BOT_TOKEN` 으로 환경 변수 확인 |
| 권한 오류 | 봇에게 먼저 메시지를 보냈는지 확인 |
| Hook 미작동 | `~/.claude/settings.json` JSON 문법 오류 확인 |
| 그룹 채팅 알림 안됨 | Chat ID가 음수인지 확인 (그룹은 `-123456789` 형식) |

## 환경 변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `CLAUDE_TELEGRAM_NOTIFY_ENABLED` | `1`이어야 알림 발송 (필수) | `1` |
| `TELEGRAM_BOT_TOKEN` | BotFather에서 발급받은 토큰 | `1234567890:ABC...` |
| `TELEGRAM_CHAT_ID` | 알림 받을 채팅 ID | `123456789` |
| `TELEGRAM_DEBUG` | 디버그 모드 활성화 (선택) | `1` |

> **참고**: `CLAUDE_TELEGRAM_NOTIFY_ENABLED=1`이 설정되어 있지 않으면 스킬이 설치되어 있어도 알림이 발송되지 않습니다.

## 디버그 모드

문제 해결을 위해 Claude Code가 전달하는 데이터를 확인하려면:

```bash
export TELEGRAM_DEBUG=1
```

설정 후 알림 발생 시 터미널에 hook 입력 JSON이 출력됩니다.

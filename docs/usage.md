# TIL MCP 서버 사용 가이드

## 1. 설치

### 가상환경 설정 및 의존성 설치

```bash
cd /Users/ram/programming/vibecoding/mcp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. 서버 실행

### 직접 실행 (테스트용)

```bash
source venv/bin/activate
python -m src.til_server.server
```

서버는 stdio 전송 방식으로 동작하므로 직접 실행하면 입력 대기 상태가 됩니다.
실제 사용은 Claude Code에서 MCP 서버로 등록하여 사용합니다.

## 3. Claude Code에서 MCP 서버 연동

### 방법 1: CLI로 등록 (권장)

```bash
claude mcp add --transport stdio til-server -- \
  /Users/ram/programming/vibecoding/mcp/venv/bin/python \
  -m src.til_server.server
```

### 방법 2: .mcp.json 파일 직접 작성

프로젝트 루트에 `.mcp.json` 파일을 생성:

```json
{
  "mcpServers": {
    "til-server": {
      "command": "/Users/ram/programming/vibecoding/mcp/venv/bin/python",
      "args": ["-m", "src.til_server.server"]
    }
  }
}
```

### 등록 확인

```bash
claude mcp list
```

Claude Code 내부에서 `/mcp` 명령으로도 확인 가능합니다.

## 4. 사용 예시

Claude Code에서 자연어로 사용할 수 있습니다:

### TIL 작성
> "오늘 Python 데코레이터에 대해 배운 내용을 TIL로 기록해줘"

### TIL 검색
> "MCP 관련 TIL을 검색해줘"

### 통계 확인
> "이번 주 학습 통계 보여줘"

### 주간 회고
> "이번 주 학습 회고를 작성해줘"

### 내보내기
> "이번 주 TIL을 Markdown으로 내보내줘"

## 5. 제공 기능

### Tools (데이터 변경)
| Tool | 설명 |
|------|------|
| `create_til` | 새 TIL 항목 작성 |
| `update_til` | 기존 TIL 수정 |
| `delete_til` | TIL 삭제 |
| `search_til` | 키워드 검색 |
| `add_tag` | 태그 추가 |
| `export_til` | Markdown 내보내기 |

### Resources (읽기 전용)
| URI | 설명 |
|-----|------|
| `til://list` | 전체 TIL 목록 |
| `til://list/today` | 오늘 TIL |
| `til://list/week` | 이번 주 TIL |
| `til://{id}` | 특정 TIL 상세 |
| `til://tags` | 태그 목록 |
| `til://categories` | 카테고리 목록 |
| `til://stats` | 학습 통계 |

### Prompts (프롬프트 템플릿)
| Prompt | 설명 |
|--------|------|
| `write_til` | TIL 작성 도우미 |
| `weekly_review` | 주간 학습 회고 |
| `suggest_topics` | 학습 주제 추천 |
| `summarize_learnings` | 기간별 학습 요약 |

## 6. 데이터 위치

- SQLite 데이터베이스: `data/til.db`
- 서버 시작 시 자동으로 `data/` 디렉토리와 테이블이 생성됩니다.

## 7. 프로젝트 구조

```
mcp/
├── src/til_server/
│   ├── __init__.py      # 패키지 초기화
│   ├── server.py        # FastMCP 서버 메인
│   ├── db.py            # SQLite DB 로직
│   ├── tools.py         # Tool 정의 (CRUD)
│   ├── resources.py     # Resource 정의 (조회)
│   └── prompts.py       # Prompt 정의 (템플릿)
├── data/til.db          # SQLite DB (자동 생성)
├── requirements.txt     # Python 의존성
└── docs/usage.md        # 이 문서
```

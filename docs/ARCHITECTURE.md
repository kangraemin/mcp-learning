# Architecture

## 프로젝트 개요

**til-server**: TIL(Today I Learned) 지식 관리 MCP 서버.
FastMCP 기반으로 Claude Code 등 MCP 클라이언트에 TIL 도구를 제공한다.

## 현재 구조

```
src/til_server/
├── server.py          # FastMCP 인스턴스 + 엔트리포인트
├── storage.py         # 하위 호환 래퍼 (github_storage 재노출)
├── github_storage.py  # GitHub API 기반 저장소 구현
├── tools.py           # MCP Tool 정의 (create/update/delete/search/tag/export)
├── resources.py       # MCP Resource 정의 (list/today/week/detail/tags/stats)
├── prompts.py         # MCP Prompt 정의 (write/review/suggest)
└── db.py              # (레거시, storage.py로 대체)
```

## MCP 프리미티브

| 프리미티브 | 역할 | 예시 |
|-----------|------|------|
| Tool | 데이터 변경 (POST/PUT/DELETE) | create_til, update_til, delete_til |
| Resource | 읽기 전용 (GET) | til://list, til://today |
| Prompt | LLM 지시 템플릿 | write_til, weekly_review |

## 스토리지 레이어

현재: **GitHub API** 단일 백엔드
- 파일 경로: `tils/YYYY-MM-DD-{slug}.md`
- 포맷: YAML frontmatter + Markdown body
- 인증: GITHUB_TOKEN 환경변수 또는 `gh auth token`

### 목표 아키텍처 (Notion 백엔드 추가 후)

```
storage.py (StorageBackend 추상 클래스)
├── github_storage.py  (GitHubBackend)
└── notion_storage.py  (NotionBackend)

config.py              # ~/.til/config.json 관리
```

**TIL 데이터 모델** (공통):
```python
{
    "id": int,           # YYYYMMDDHHMMSS
    "title": str,
    "content": str,      # Markdown
    "category": str,     # 기본값: "general"
    "tags": list[str],
    "created_at": str,   # ISO 8601
    "updated_at": str,   # ISO 8601
}
```

## 설정 파일

`~/.til/config.json`:
```json
{
    "backend": "github",       // "github" | "notion"
    "github": {
        "repo": "username/til-notes"
    },
    "notion": {
        "token": "secret_...",
        "database_id": "..."
    }
}
```

## 의존성

- `mcp>=1.26.0` — FastMCP 프레임워크
- `python-frontmatter>=1.1.0` — YAML frontmatter 파싱
- `notion-client` — Notion API (백엔드 추가 시)

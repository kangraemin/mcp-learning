# Coding Conventions

## 언어 & 버전

- Python 3.11+
- 타입 힌트 필수 (`from __future__ import annotations` 사용)

## 파일 구조

- 모듈마다 상단에 docstring으로 역할 설명
- 함수 단위로 `# --- 섹션명 ---` 구분선 사용

## 네이밍

| 대상 | 규칙 | 예시 |
|------|------|------|
| 모듈 내부 함수 | `_snake_case` (언더스코어 prefix) | `_get_token()` |
| 공개 API 함수 | `snake_case` | `create_til()` |
| 예외 클래스 | `PascalCaseError` | `GitHubStorageError` |
| 상수/캐시 | `_UPPER_CASE` 또는 `_lower_cache` | `_token_cache` |

## 에러 처리

- 스토리지 레이어: 도메인 예외(`StorageError` 서브클래스) 발생
- Tool 레이어: `ValueError` (입력 오류), `LookupError` (찾을 수 없음)
- FastMCP가 예외를 MCP 에러 응답으로 자동 변환

## 스토리지 백엔드 인터페이스

모든 백엔드는 동일한 공개 함수를 구현해야 한다:

```python
def create_til(title, content, category, tags) -> dict
def update_til(til_id, title, content, category, tags) -> dict
def delete_til(til_id) -> bool
def search_tils(query, tag, category) -> list[dict]
def add_tag(til_id, tag) -> dict
def get_til_by_id(til_id) -> dict | None
def list_all_tils() -> list[dict]
def list_today_tils() -> list[dict]
def list_week_tils() -> list[dict]
def get_stats() -> dict
def get_tils_for_export(til_id, date_from, date_to) -> list[dict]
def get_tags() -> list[str]
def get_categories() -> list[str]
```

## 커밋 메시지

`~/.claude/rules/git-rules.md` 참조. 기본값 한글.

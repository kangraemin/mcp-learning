# til-server - Development Guide

프로젝트 전체 규칙의 허브. 모든 에이전트(`~/.claude/agents/`)가 이 문서를 먼저 읽는다.

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 앱 이름 | **til-server** |
| 설명 | TIL(Today I Learned) 지식 관리 MCP 서버 |
| 언어 | Python 3.11+ |
| 프레임워크 | FastMCP |
| 현재 스토리지 | GitHub API (마크다운 파일) |
| PyPI | `uvx til-server` |
| GitHub | https://github.com/kangraemin/mcp-learning |

## 2. 상세 가이드

| 문서 | 내용 |
|------|------|
| [Architecture](docs/ARCHITECTURE.md) | 모듈 구조, 스토리지 레이어, 목표 아키텍처 |
| [Coding Conventions](docs/CODING_CONVENTIONS.md) | 네이밍, 에러 처리, 백엔드 인터페이스 |
| [Testing](docs/TESTING.md) | 테스트 프레임워크, 검증 명령, 전략 |
| [Git Rules](~/.claude/rules/git-rules.md) | 커밋, 푸시, PR 규칙 (글로벌) |

## 3. 소스 구조

```
src/til_server/
├── server.py          # FastMCP 인스턴스 + 엔트리포인트
├── storage.py         # 백엔드 라우터 (config 기반으로 백엔드 선택)
├── github_storage.py  # GitHub API 백엔드
├── notion_storage.py  # Notion API 백엔드 (추가 예정)
├── config.py          # ~/.til/config.json 관리 (추가 예정)
├── tools.py           # MCP Tool 정의
├── resources.py       # MCP Resource 정의
└── prompts.py         # MCP Prompt 정의
```

## 4. 개발 중인 피처

### Notion 백엔드 + 마이그레이션

**목표:**
- MCP 서버 첫 실행 시 백엔드 선택 (GitHub / Notion)
- 설정은 `~/.til/config.json`에 저장
- `migrate_backend` MCP 툴로 양방향 마이그레이션 지원

**구현 순서:**
1. `config.py` — 설정 파일 관리
2. `storage.py` 리팩토링 — 백엔드 추상화 + 동적 선택
3. `notion_storage.py` — Notion API 백엔드 구현
4. `tools.py` — `migrate_backend` 툴 추가
5. `server.py` — 첫 실행 시 setup 안내

## 5. Git 컨벤션

`~/.claude/rules/git-rules.md` 참조.
- 커밋 언어: 한글 (COMMIT_LANG 미설정 시)
- 커밋 후 반드시 푸시

## 6. 빌드 검증

```bash
python -c "from til_server.server import mcp; print('OK')"
pytest tests/ -v
```

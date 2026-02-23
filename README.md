# TIL MCP 서버

> **GitHub**: https://github.com/kangraemin/mcp-learning

학습 내용(TIL: Today I Learned)과 대화 중 논의한 것들을 기록하고, 검색하고, 회고해주는 MCP 서버.

Claude에게 자연어로 말하면 알아서 GitHub에 마크다운 파일로 저장한다.

---

## 이런 게 됩니다

| 말하면 | Claude가 하는 일 |
|--------|-----------------|
| "오늘 Python 배운 거 기록해줘" | TIL 작성해서 GitHub에 저장 |
| "방금 토큰 최적화 논의한 거 정리해줘" | 대화 내용 요약해서 GitHub에 저장 |
| "이번 주 뭐 배웠지?" | 이번 주 기록 꺼내서 보여줌 |
| "MCP 관련 기록 찾아줘" | 키워드로 검색해서 결과 보여줌 |
| "주간 회고 써줘" | 이번 주 기록 분석해서 회고문 작성 |

---

## 설치

### 사전 준비

- [Claude Code](https://claude.ai/claude-code) 설치
- [gh CLI](https://cli.github.com) 설치 + 로그인

```bash
# gh CLI 설치 후
gh auth login
```

> **Windows**: [gh CLI Windows 설치](https://github.com/cli/cli/releases/latest) 에서 `.msi` 다운로드

### uv 설치

**macOS / Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### MCP 서버 등록

```bash
claude mcp add -s user --transport stdio til-server \
  -- uvx --refresh --from git+https://github.com/kangraemin/mcp-learning til-server
```

**Windows (PowerShell)**
```powershell
claude mcp add -s user --transport stdio til-server `
  -- uvx --refresh --from git+https://github.com/kangraemin/mcp-learning til-server
```

> `-s user` 없이 실행하면 현재 프로젝트에만 등록됩니다. 모든 프로젝트에서 쓰려면 `-s user`를 붙이세요.

Claude Code를 재시작하면 끝.

---

## 첫 사용

Claude Code에서 아무거나 기록해보자:

```
오늘 배운 거 기록해줘
```

처음 사용 시 `{GitHub유저명}/til-notes` 레포가 없으면 자동으로 생성된다.

이후 모든 TIL은 해당 레포에 마크다운 파일로 저장된다:
```
til-notes/
  tils/
    2026-02-23-python-.md
    2026-02-23-mcp-.md
```

---

## 다른 레포에 저장하고 싶다면

```bash
claude mcp add -s user --transport stdio til-server \
  -e TIL_GITHUB_REPO=username/my-notes \
  -- uvx --refresh --from git+https://github.com/kangraemin/mcp-learning til-server
```

gh CLI 없이 토큰으로 직접 인증하려면:
```bash
claude mcp add -s user --transport stdio til-server \
  -e TIL_GITHUB_REPO=username/my-notes \
  -e GITHUB_TOKEN=ghp_xxxx \
  -- uvx --refresh --from git+https://github.com/kangraemin/mcp-learning til-server
```

---

## 동작 원리

```
사용자: "Python 배운 거 기록해줘"
    ↓
Claude Code → Claude AI (어떤 도구 쓸지 판단)
    ↓
Claude AI → "create_til 써줘"
    ↓
Claude Code → TIL MCP 서버 (로컬에서 실행 중)
    ↓
TIL MCP 서버 → GitHub API → til-notes 레포에 .md 파일 생성
```

인터넷 구간: Claude Code ↔ Anthropic AI 서버
로컬 구간: Claude Code ↔ MCP 서버
저장소: GitHub 레포 (마크다운 파일)

---

## 제공하는 기능

### Tools (행동)
| 이름 | 설명 |
|------|------|
| `create_til` | TIL 작성 및 대화 내용 요약 저장 |
| `update_til` | 기존 TIL 수정 |
| `delete_til` | TIL 삭제 |
| `search_til` | 키워드/태그/카테고리로 검색 |
| `add_tag` | 태그 추가 |
| `export_til` | Markdown으로 내보내기 |

### Resources (조회)
| URI | 설명 |
|-----|------|
| `til://list` | 전체 목록 |
| `til://list/today` | 오늘 기록 |
| `til://list/week` | 최근 7일 기록 |
| `til://{id}` | 특정 TIL 상세 |
| `til://tags` | 태그 목록 |
| `til://stats` | 학습 통계 |

### Prompts (템플릿)
| 이름 | 설명 |
|------|------|
| `write_til` | TIL 작성 가이드 |
| `weekly_review` | 주간 회고 생성 |
| `suggest_topics` | 다음 학습 주제 추천 |
| `summarize_learnings` | 기간별 학습 요약 |
| `discussion_recap` | 대화 논의 내용 정리 |

---

## 기술 스택

| 항목 | 내용 |
|------|------|
| 언어 | Python 3.11+ |
| MCP 프레임워크 | FastMCP |
| 저장소 | GitHub (마크다운 파일) |
| 전송 방식 | stdio |

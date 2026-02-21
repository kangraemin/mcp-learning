# MCP 서버 기획서

## 1. 아이디어 3개 비교 분석

### 아이디어 A: Smart Bookmark Manager (스마트 북마크 관리)

**개요**: URL을 저장하고 태그/카테고리로 관리하며, 웹 페이지 메타데이터를 자동 수집하는 MCP 서버

| 항목 | 평가 |
|------|------|
| 학습 적합도 | ★★★★☆ - tool/resource/prompt 모두 활용 가능 |
| 실용성 | ★★★☆☆ - 브라우저 북마크와 기능 중복 |
| 복잡도 | ★★★☆☆ - 웹 스크래핑(httpx, beautifulsoup) 의존성 추가 |
| MCP 개념 커버리지 | tool(CRUD), resource(목록 조회), prompt(정리 제안) |

**장점**: 웹 크롤링이라는 재미 요소, 실제 데이터 다룸
**단점**: 웹 스크래핑 안정성 이슈, 브라우저 확장 프로그램과 역할 중복

---

### 아이디어 B: TIL(Today I Learned) 지식 관리

**개요**: 개발 학습 내용을 기록·검색·요약하는 MCP 서버. SQLite로 저장하고, 태그/카테고리로 분류하며, Claude가 주간 회고나 학습 통계를 생성

| 항목 | 평가 |
|------|------|
| 학습 적합도 | ★★★★★ - tool/resource/prompt 구분이 가장 명확 |
| 실용성 | ★★★★★ - 개발자가 매일 실제로 사용 가능 |
| 복잡도 | ★★☆☆☆ - SQLite + 순수 Python만으로 구현 가능 |
| MCP 개념 커버리지 | tool(CRUD+검색), resource(목록/통계/개별조회), prompt(요약/회고 템플릿) |

**장점**: 학습 프로젝트와 시너지(MCP 배우면서 TIL 기록), 외부 의존성 최소, 프론트엔드 불필요
**단점**: 기능이 단순해 보일 수 있음 (하지만 학습용으로는 장점)

---

### 아이디어 C: 프로젝트 타임 트래커

**개요**: 코딩 작업 시간을 기록하고, 프로젝트별 통계와 일일/주간 보고서를 생성하는 MCP 서버

| 항목 | 평가 |
|------|------|
| 학습 적합도 | ★★★★☆ - tool/resource/prompt 활용 가능 |
| 실용성 | ★★★★☆ - 프리랜서/개발자에게 유용 |
| 복잡도 | ★★★☆☆ - 타이머 상태 관리가 다소 복잡 |
| MCP 개념 커버리지 | tool(타이머 제어), resource(통계 조회), prompt(보고서 생성) |

**장점**: 시간 추적은 보편적 니즈, 통계 시각화 가능성
**단점**: 타이머 상태 관리 복잡 (MCP 서버는 stateless가 이상적), 기존 worklog hook과 역할 중복 가능

---

### 비교 요약표

| 기준 | A. 북마크 | B. TIL ✅ | C. 타임트래커 |
|------|-----------|-----------|---------------|
| 학습 적합도 | ★★★★ | ★★★★★ | ★★★★ |
| 실용성 | ★★★ | ★★★★★ | ★★★★ |
| 구현 난이도(낮을수록 좋음) | ★★★ | ★★ | ★★★ |
| MCP 개념 커버리지 | 좋음 | **최고** | 좋음 |
| 외부 의존성 | httpx, bs4 | 없음 | 없음 |
| 프론트엔드 필요 | 선택 | **불필요** | 선택 |

---

## 2. 최종 추천: TIL(Today I Learned) 지식 관리 MCP 서버

### 선정 이유

1. **MCP 개념 학습에 최적**: tool(데이터 변경), resource(데이터 조회), prompt(템플릿)의 경계가 가장 뚜렷하여 "언제 tool을 쓰고 언제 resource를 쓰는가"를 명확히 학습 가능
2. **실용성**: MCP를 학습하면서 동시에 TIL을 기록 → 학습의 선순환
3. **최소 복잡도**: SQLite + 순수 Python만으로 구현. 외부 API나 크롤링 없이도 충분히 동작
4. **프론트엔드 불필요**: Claude Code 자체가 UI 역할을 하므로 별도 프론트엔드 없이 완전한 사용자 경험 제공
5. **확장 가능**: 기본 구현 후 Markdown 내보내기, GitHub 연동, 통계 시각화 등으로 확장 가능

---

## 3. 기능 목록

### Tools (행동/변경 - 데이터를 생성·수정·삭제하는 작업)

| Tool 이름 | 설명 | 파라미터 |
|-----------|------|----------|
| `create_til` | 새 TIL 항목 작성 | `title`, `content`, `tags` (선택), `category` (선택) |
| `update_til` | 기존 TIL 수정 | `til_id`, `title` (선택), `content` (선택), `tags` (선택) |
| `delete_til` | TIL 삭제 | `til_id` |
| `search_til` | TIL 키워드 검색 | `query`, `tag` (선택), `category` (선택) |
| `add_tag` | TIL에 태그 추가 | `til_id`, `tag` |
| `export_til` | TIL을 Markdown 파일로 내보내기 | `til_id` 또는 `date_range` |

### Resources (조회 - 읽기 전용 데이터 접근)

| Resource URI | 설명 |
|-------------|------|
| `til://list` | 전체 TIL 목록 (최근순) |
| `til://list/today` | 오늘 작성한 TIL 목록 |
| `til://list/week` | 이번 주 작성한 TIL 목록 |
| `til://{til_id}` | 특정 TIL 상세 내용 (Resource Template) |
| `til://tags` | 전체 태그 목록과 사용 횟수 |
| `til://categories` | 전체 카테고리 목록 |
| `til://stats` | 학습 통계 (총 개수, 일별/주별 추이, 인기 태그) |

### Prompts (미리 정의된 프롬프트 템플릿)

| Prompt 이름 | 설명 | 파라미터 |
|-------------|------|----------|
| `write_til` | TIL 작성을 도와주는 프롬프트 | `topic` - 학습한 주제 |
| `weekly_review` | 주간 학습 회고 생성 프롬프트 | `week` (선택) - 특정 주차 |
| `suggest_topics` | 학습 이력 기반 다음 학습 주제 추천 | `category` (선택) |
| `summarize_learnings` | 특정 기간 학습 내용 요약 | `date_from`, `date_to` |

---

## 4. 프론트엔드 필요 여부

### 결론: **불필요**

### 이유

1. **Claude Code가 UI**: MCP 서버의 소비자(client)는 Claude Code 또는 다른 LLM 클라이언트. 사용자는 자연어로 "오늘 배운 거 기록해줘"라고 말하면 Claude가 tool을 호출하여 처리
2. **MCP 학습 집중**: 프론트엔드 개발에 시간을 쓰면 MCP 핵심 학습에서 벗어남
3. **충분한 인터페이스**: resource를 통해 데이터 조회가 가능하고, prompt를 통해 구조화된 상호작용이 가능하므로 별도 UI 없이도 완전한 사용자 경험 제공
4. **나중에 추가 가능**: 필요하다면 FastMCP의 streamable-http 전송을 활용하여 나중에 웹 대시보드를 추가할 수 있음

---

## 5. 기술 스택

| 항목 | 선택 | 이유 |
|------|------|------|
| 프레임워크 | FastMCP (Python) | MCP 서버 구축 표준 |
| 데이터베이스 | SQLite | 설치 불필요, 단일 파일, Python 내장 |
| 전송 방식 | stdio (개발) → streamable-http (선택) | Claude Code 연동에 stdio가 가장 간단 |
| 의존성 | fastmcp, sqlite3 (내장) | 최소 의존성 |

---

## 6. 데이터 모델

```sql
CREATE TABLE tils (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE til_tags (
    til_id INTEGER REFERENCES tils(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (til_id, tag_id)
);
```

---

## 7. 프로젝트 구조 (예상)

```
mcp/
├── src/
│   └── til_server/
│       ├── __init__.py
│       ├── server.py          # FastMCP 서버 메인
│       ├── db.py              # SQLite 데이터베이스 로직
│       ├── tools.py           # Tool 정의
│       ├── resources.py       # Resource 정의
│       └── prompts.py         # Prompt 정의
├── data/
│   └── til.db                 # SQLite DB 파일
├── docs/
│   ├── plan.md                # 이 문서
│   └── research.md            # FastMCP 연구 결과
├── tests/
│   └── test_server.py
├── pyproject.toml
└── README.md
```

---

## 8. 구현 우선순위

| 단계 | 작업 | 설명 |
|------|------|------|
| 1단계 | DB + 기본 Tool | SQLite 설정, `create_til`, `search_til` 구현 |
| 2단계 | Resource 추가 | `til://list`, `til://{id}`, `til://stats` 구현 |
| 3단계 | Prompt 추가 | `write_til`, `weekly_review` 프롬프트 구현 |
| 4단계 | Claude Code 연동 | `.mcp.json` 설정으로 실제 연동 테스트 |
| 5단계 | 나머지 기능 | 나머지 tool/resource/prompt + 테스트 |

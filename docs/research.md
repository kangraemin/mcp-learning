# FastMCP Python SDK 연구 결과

> 조사일: 2026-02-21
> MCP Python SDK 버전: 1.26.0 (프로젝트 venv 설치 확인)
> FastMCP는 `mcp.server.fastmcp` 모듈로 공식 SDK에 내장됨

---

## 1. FastMCP 서버 구조

### 1.1 기본 초기화

FastMCP는 Flask/FastAPI와 유사한 데코레이터 기반 API를 제공한다.
`mcp.server.fastmcp.FastMCP` 클래스를 인스턴스화하고, 데코레이터로 tool/resource/prompt를 등록한다.

```python
from mcp.server.fastmcp import FastMCP

# 서버 인스턴스 생성
mcp = FastMCP("TIL Server")

if __name__ == "__main__":
    mcp.run()  # 기본: stdio 전송
```

**주요 생성자 옵션:**
- `name`: 서버 이름 (필수)
- `json_response`: JSON 응답 모드 활성화 (기본 False)
- `lifespan`: 서버 생명주기 관리 함수 (DB 연결 등)

### 1.2 Tool 데코레이터 (`@mcp.tool()`)

Tool은 LLM이 **행동/변경**을 수행할 때 사용한다. 함수 시그니처에서 자동으로 JSON Schema가 생성되며, docstring이 tool 설명이 된다.

```python
@mcp.tool()
def create_til(title: str, content: str, tags: list[str] | None = None) -> dict:
    """새 TIL 항목을 생성합니다.

    Args:
        title: TIL 제목
        content: 학습 내용 (Markdown 지원)
        tags: 태그 목록 (선택)
    """
    # DB에 저장하는 로직
    return {"id": 1, "title": title, "status": "created"}
```

**비동기 tool + Context 활용:**

```python
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

mcp = FastMCP("TIL Server")

@mcp.tool()
async def search_til(
    query: str,
    ctx: Context[ServerSession, None]
) -> list[dict]:
    """TIL을 키워드로 검색합니다."""
    await ctx.info(f"검색 시작: {query}")

    # 진행률 보고
    await ctx.report_progress(progress=1, total=3, message="DB 조회 중")
    results = await do_search(query)

    await ctx.report_progress(progress=3, total=3, message="완료")
    return results
```

**Context 객체가 제공하는 기능:**
- `ctx.debug()`, `ctx.info()`, `ctx.warning()`, `ctx.error()` — 로그 레벨별 메시지
- `ctx.report_progress(progress, total, message)` — 진행률 보고
- `ctx.session.send_resource_list_changed()` — 리소스 변경 알림

**Pydantic 모델 반환:**

```python
from pydantic import BaseModel, Field

class TilItem(BaseModel):
    id: int
    title: str = Field(description="TIL 제목")
    content: str
    tags: list[str] = []

@mcp.tool()
def get_til(til_id: int) -> TilItem:
    """특정 TIL을 조회합니다."""
    return TilItem(id=til_id, title="MCP 배우기", content="...", tags=["mcp"])
```

### 1.3 Resource 데코레이터 (`@mcp.resource()`)

Resource는 **읽기 전용 데이터 접근**을 위한 것이다. REST API의 GET 엔드포인트와 유사하며, 부작용(side effect)이 없어야 한다.

```python
import json

# 정적 리소스
@mcp.resource("til://stats")
def get_stats() -> str:
    """학습 통계를 조회합니다."""
    stats = {"total": 42, "this_week": 5, "top_tag": "python"}
    return json.dumps(stats, ensure_ascii=False, indent=2)

# 템플릿 리소스 (URI 파라미터)
@mcp.resource("til://{til_id}")
def get_til_detail(til_id: str) -> str:
    """특정 TIL 상세 내용을 조회합니다."""
    # DB에서 til_id로 조회
    return json.dumps({"id": til_id, "title": "...", "content": "..."})

# 비동기 리소스 + Context
@mcp.resource("til://list")
async def list_tils(ctx: Context) -> str:
    """전체 TIL 목록을 조회합니다."""
    await ctx.info("TIL 목록 조회 중")
    # DB 조회 로직
    return json.dumps([{"id": 1, "title": "MCP 배우기"}])
```

**Tool vs Resource 구분 기준:**
| 구분 | Tool | Resource |
|------|------|----------|
| 목적 | 행동/변경 수행 | 데이터 조회 |
| 부작용 | 있을 수 있음 (CRUD) | 없어야 함 (읽기 전용) |
| 비유 | POST/PUT/DELETE | GET |
| 예시 | `create_til`, `delete_til` | `til://list`, `til://stats` |

### 1.4 Prompt 데코레이터 (`@mcp.prompt()`)

Prompt는 미리 정의된 **프롬프트 템플릿**이다. Claude가 특정 작업을 수행할 때 구조화된 지시를 제공한다.

```python
@mcp.prompt()
def write_til(topic: str) -> str:
    """TIL 작성을 도와주는 프롬프트"""
    return f"""다음 주제에 대한 TIL(Today I Learned)을 작성해주세요.

주제: {topic}

작성 가이드:
1. 제목은 명확하고 간결하게
2. 핵심 내용을 요약
3. 코드 예제가 있다면 포함
4. 참고 자료 링크 추가

적절한 태그와 카테고리도 제안해주세요."""

@mcp.prompt()
def weekly_review(week: str = "this") -> str:
    """주간 학습 회고를 생성하는 프롬프트"""
    return f"""이번 주({week})에 작성한 TIL들을 분석하여 주간 학습 회고를 작성해주세요.

포함할 내용:
1. 이번 주 학습 요약
2. 가장 인상 깊었던 학습
3. 부족한 부분 / 다음 주 학습 계획
4. 학습 패턴 분석 (어떤 카테고리에 집중했는지)"""
```

### 1.5 Lifespan (생명주기 관리)

DB 연결, 외부 리소스 초기화/정리에 `lifespan` 패턴을 사용한다. **TIL 서버에서 SQLite 연결 관리에 핵심적인 패턴이다.**

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
import aiosqlite

from mcp.server.fastmcp import Context, FastMCP


@dataclass
class AppContext:
    """앱 전역 컨텍스트 - tool/resource에서 접근 가능"""
    db: aiosqlite.Connection


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """서버 시작/종료 시 DB 연결 관리"""
    # 서버 시작 시 실행
    db = await aiosqlite.connect("data/til.db")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")

    try:
        yield AppContext(db=db)
    finally:
        # 서버 종료 시 실행
        await db.close()


mcp = FastMCP("TIL Server", lifespan=app_lifespan)


@mcp.tool()
async def create_til(
    title: str,
    content: str,
    ctx: Context[ServerSession, AppContext]
) -> dict:
    """새 TIL을 생성합니다."""
    app = ctx.request_context.lifespan_context
    cursor = await app.db.execute(
        "INSERT INTO tils (title, content) VALUES (?, ?)",
        (title, content)
    )
    await app.db.commit()
    return {"id": cursor.lastrowid, "title": title}
```

> **참고**: 동기 SQLite(sqlite3)를 사용할 경우 lifespan을 사용하지 않고 모듈 수준에서 DB 연결을 관리하는 것이 더 간단할 수 있다. aiosqlite는 비동기 tool과 함께 사용할 때 유용하다.

---

## 2. 전송 방식(Transport) 비교

### 2.1 개요

| 전송 방식 | 사용 환경 | 통신 방식 | 클라이언트 수 |
|-----------|----------|-----------|-------------|
| **stdio** | 로컬 개발, CLI 통합 | stdin/stdout | 1 (프로세스당) |
| **streamable-http** | 프로덕션, 원격 배포 | HTTP (단일 엔드포인트) | 다수 |
| **SSE** (레거시) | 이전 클라이언트 호환 | Server-Sent Events | 다수 |

### 2.2 stdio (기본값, 추천 - 로컬 개발용)

클라이언트가 서버 프로세스를 직접 실행하고, stdin/stdout으로 MCP 메시지를 교환한다.

```python
# 방법 1: 기본 실행 (stdio)
if __name__ == "__main__":
    mcp.run()  # transport 미지정 시 stdio

# 방법 2: 명시적 지정
if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**장점:**
- 설정이 가장 간단
- Claude Code, Claude Desktop에서 바로 사용 가능
- 네트워크 설정 불필요

**단점:**
- 세션당 별도 프로세스 필요
- 원격 접근 불가

**Claude Code에서 stdio 서버 실행:**
```bash
claude mcp add --transport stdio til-server -- python /path/to/server.py
```

### 2.3 streamable-http (프로덕션 추천)

단일 HTTP 엔드포인트(`/mcp`)로 통신하며, 필요시 SSE로 스트리밍 업그레이드한다.

```python
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
```

서버 접속 URL: `http://127.0.0.1:8000/mcp`

**장점:**
- 다수 클라이언트 동시 접속
- 네트워크를 통한 원격 접근
- ASGI 서버(uvicorn)와 통합 가능

**단점:**
- 네트워크 설정 필요 (포트, 방화벽 등)
- stdio보다 설정이 복잡

**ASGI 프로덕션 배포:**
```python
def create_app():
    mcp = FastMCP("TIL Server")
    # tool, resource, prompt 등록...
    return mcp.http_app()

app = create_app()
# uvicorn으로 실행: uvicorn server:app --host 0.0.0.0 --port 8000
```

### 2.4 SSE (레거시 - 신규 프로젝트 비추천)

```python
if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=8000)
```

> **비추천 사유**: SSE는 서버→클라이언트 단방향 스트리밍만 지원하며, 공식적으로 deprecated 상태이다. 새 프로젝트에서는 반드시 streamable-http를 사용할 것.

### 2.5 TIL 서버 권장 전략

1. **개발 단계**: `stdio` — Claude Code와 바로 연동, 디버깅 간편
2. **테스트 단계**: `streamable-http` — MCP Inspector 등 외부 도구와 테스트
3. **실제 사용**: `stdio` — Claude Code에서 일상적으로 사용할 때 가장 간편

---

## 3. 에러 처리 패턴

### 3.1 기본 예외 처리

FastMCP는 tool 함수에서 발생하는 예외를 자동으로 MCP 에러 응답으로 변환한다.

```python
@mcp.tool()
def delete_til(til_id: int) -> dict:
    """TIL을 삭제합니다."""
    if til_id <= 0:
        raise ValueError(f"유효하지 않은 TIL ID: {til_id}")

    # DB에서 삭제
    deleted = db_delete(til_id)
    if not deleted:
        raise LookupError(f"TIL을 찾을 수 없습니다: {til_id}")

    return {"status": "deleted", "id": til_id}
```

### 3.2 Context를 활용한 로깅

에러를 발생시키기 전에 Context를 통해 상세 로그를 남길 수 있다.

```python
@mcp.tool()
async def update_til(
    til_id: int,
    title: str | None = None,
    content: str | None = None,
    ctx: Context[ServerSession, None] = None
) -> dict:
    """TIL을 수정합니다."""
    if not title and not content:
        await ctx.warning("수정할 내용이 없습니다")
        raise ValueError("title 또는 content 중 하나는 제공해야 합니다")

    try:
        result = await db_update(til_id, title=title, content=content)
        await ctx.info(f"TIL #{til_id} 수정 완료")
        return result
    except Exception as e:
        await ctx.error(f"TIL #{til_id} 수정 실패: {e}")
        raise
```

### 3.3 입력 검증 (Pydantic 활용)

FastMCP는 Pydantic과 통합되어 있으므로 타입 힌트만으로 자동 검증이 가능하다. 추가 검증이 필요한 경우:

```python
from pydantic import BaseModel, Field, field_validator

class CreateTilInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list, max_length=10)
    category: str = "general"

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        return [tag.lower().strip() for tag in v if tag.strip()]

# tool에서 Pydantic 모델을 파라미터로 사용하지 않고,
# 개별 파라미터로 받아 내부에서 검증하는 패턴이 더 일반적:
@mcp.tool()
def create_til(title: str, content: str, tags: list[str] | None = None) -> dict:
    """새 TIL을 생성합니다."""
    # 간단한 검증
    if not title.strip():
        raise ValueError("제목은 비어있을 수 없습니다")
    if len(title) > 200:
        raise ValueError("제목은 200자를 초과할 수 없습니다")
    # ...
```

### 3.4 에러 처리 베스트 프랙티스

1. **표준 Python 예외 사용**: `ValueError`, `LookupError`, `PermissionError` 등
2. **에러 메시지는 사용자 친화적으로**: LLM이 에러 메시지를 보고 재시도 판단
3. **Context 로깅 활용**: `ctx.error()`로 상세 에러 정보 기록
4. **조용한 실패 방지**: 에러 발생 시 명확히 raise할 것

---

## 4. Claude Code에서 MCP 서버 연동 설정

### 4.1 설정 파일 위치와 범위(Scope)

| 범위 | 설정 파일 | 용도 |
|------|----------|------|
| **local** (기본) | `~/.claude.json` (프로젝트 경로별) | 개인 전용, 현재 프로젝트만 |
| **project** | 프로젝트 루트 `.mcp.json` | 팀 공유, git에 커밋 가능 |
| **user** | `~/.claude.json` | 모든 프로젝트에서 사용 |

> **주의**: MCP 서버 설정은 `~/.claude/settings.json`이 아닌 `~/.claude.json` 또는 `.mcp.json`에 저장된다.

### 4.2 CLI로 MCP 서버 추가

**stdio 서버 추가 (로컬 Python 서버):**
```bash
# 기본 추가 (local scope)
claude mcp add --transport stdio til-server -- python /Users/ram/programming/vibecoding/mcp/src/til_server/server.py

# venv의 Python을 직접 지정 (권장)
claude mcp add --transport stdio til-server -- /Users/ram/programming/vibecoding/mcp/venv/bin/python /Users/ram/programming/vibecoding/mcp/src/til_server/server.py

# 환경변수 포함
claude mcp add --transport stdio --env DB_PATH=/path/to/til.db til-server -- python server.py

# project scope (팀 공유)
claude mcp add --transport stdio --scope project til-server -- python src/til_server/server.py
```

**HTTP 서버 추가:**
```bash
# streamable-http 서버
claude mcp add --transport http til-server http://localhost:8000/mcp
```

### 4.3 `.mcp.json` 직접 작성 (프로젝트 루트)

팀과 공유할 수 있는 프로젝트 범위 설정:

```json
{
  "mcpServers": {
    "til-server": {
      "command": "python",
      "args": ["src/til_server/server.py"],
      "env": {
        "DB_PATH": "${HOME}/til-data/til.db"
      }
    }
  }
}
```

**환경변수 확장 지원:**
- `${VAR}` — 환경변수 값으로 확장
- `${VAR:-default}` — 환경변수가 없으면 기본값 사용

### 4.4 `~/.claude.json` 직접 편집 (user/local scope)

```json
{
  "mcpServers": {
    "til-server": {
      "command": "/Users/ram/programming/vibecoding/mcp/venv/bin/python",
      "args": ["/Users/ram/programming/vibecoding/mcp/src/til_server/server.py"],
      "env": {}
    }
  }
}
```

### 4.5 MCP 서버 관리 명령어

```bash
# 등록된 서버 목록
claude mcp list

# 특정 서버 상세 정보
claude mcp get til-server

# 서버 제거
claude mcp remove til-server

# Claude Code 내부에서 상태 확인
/mcp
```

### 4.6 팁

- **MCP_TIMEOUT**: 서버 시작 타임아웃 설정 (기본값 있음). `MCP_TIMEOUT=10000 claude`로 10초 설정
- **MAX_MCP_OUTPUT_TOKENS**: MCP 도구 출력 최대 토큰 (기본 25,000). `MAX_MCP_OUTPUT_TOKENS=50000 claude`
- **OAuth 인증**: `/mcp` 명령으로 원격 서버 OAuth 인증 가능
- **list_changed 알림**: MCP 서버가 동적으로 tool을 추가/제거하면 Claude Code가 자동으로 감지

---

## 5. 실제 오픈소스 MCP 서버 예제 분석

### 5.1 공식 QuickStart 예제 (MCP Python SDK)

가장 기본적인 전체 구조를 보여주는 공식 예제:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Demo", json_response=True)

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

@mcp.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    """Generate a greeting prompt"""
    styles = {
        "friendly": "Please write a warm, friendly greeting",
        "formal": "Please write a formal, professional greeting",
    }
    return f"{styles.get(style, styles['friendly'])} for someone named {name}."

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

**핵심 패턴:**
- tool/resource/prompt가 하나의 파일에 깔끔하게 정리됨
- 함수 시그니처의 타입 힌트 → JSON Schema 자동 생성
- docstring → tool/resource/prompt 설명

### 5.2 DB 연동 서버 패턴 (Low-Level + Lifespan)

프로덕션 수준의 DB 연동 패턴 (공식 SDK 예제 기반):

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
import aiosqlite

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession


@dataclass
class AppContext:
    db: aiosqlite.Connection


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    db = await aiosqlite.connect("data/til.db")
    try:
        yield AppContext(db=db)
    finally:
        await db.close()


mcp = FastMCP("DB Server", lifespan=app_lifespan)


@mcp.tool()
async def query_db(
    query: str,
    ctx: Context[ServerSession, AppContext]
) -> str:
    """데이터베이스를 조회합니다."""
    app = ctx.request_context.lifespan_context
    async with app.db.execute(query) as cursor:
        rows = await cursor.fetchall()
    return str(rows)
```

### 5.3 실제 오픈소스 프로젝트 참고

| 프로젝트 | 설명 | 참고 포인트 |
|---------|------|-----------|
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | 공식 Python SDK (FastMCP 내장) | 모든 패턴의 원본 |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | 공식 MCP 서버 모음 | 다양한 서버 구현 패턴 |
| [PrefectHQ/fastmcp](https://github.com/jlowin/fastmcp) | 독립 FastMCP 프로젝트 (v3.0) | 미들웨어, 고급 패턴 |
| [modelcontextprotocol/create-python-server](https://github.com/modelcontextprotocol/create-python-server) | Python MCP 서버 스캐폴딩 도구 | 프로젝트 초기 구조 |
| [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | MCP 서버 목록 큐레이션 | 다양한 활용 사례 |

### 5.4 TIL 서버에 적용할 핵심 패턴 요약

1. **단일 진입점 패턴**: `server.py`에서 FastMCP 인스턴스 생성, tool/resource/prompt 등록
2. **Lifespan으로 SQLite 관리**: 서버 시작 시 DB 연결, 테이블 생성, 종료 시 정리
3. **동기 함수 우선**: SQLite는 동기 sqlite3를 사용해도 충분 (간단한 서버에서는 aiosqlite가 오버스펙)
4. **Context 활용**: 검색/수정 등 시간이 걸리는 작업에서 progress 보고
5. **JSON 문자열 반환**: resource에서 `json.dumps()`로 직렬화하여 반환

---

## 6. TIL 서버 구현을 위한 추천 구조

plan.md의 구조를 기반으로, 연구 결과를 반영한 구현 방향:

```
mcp/
├── src/
│   └── til_server/
│       ├── __init__.py
│       ├── server.py       # FastMCP 인스턴스 + lifespan + 엔트리포인트
│       ├── db.py            # SQLite DB 초기화/쿼리 함수
│       ├── tools.py         # @mcp.tool() 정의 (create, update, delete, search)
│       ├── resources.py     # @mcp.resource() 정의 (list, stats, detail)
│       └── prompts.py       # @mcp.prompt() 정의 (write_til, weekly_review)
├── data/
│   └── til.db
├── .mcp.json               # Claude Code 프로젝트 설정
└── docs/
    ├── plan.md
    └── research.md          # 이 문서
```

**핵심 구현 결정 사항:**

| 결정 | 선택 | 이유 |
|------|------|------|
| DB 라이브러리 | `sqlite3` (내장) | 외부 의존성 없음, 학습용으로 충분 |
| 비동기 여부 | 동기 함수 위주 | SQLite + 단순 로직에서 async 불필요 |
| 전송 방식 | `stdio` (기본) | Claude Code 연동 가장 간편 |
| 파일 분리 | server/db/tools/resources/prompts | 관심사 분리, 유지보수 용이 |
| 에러 처리 | 표준 Python 예외 | FastMCP 자동 변환 활용 |

---

## 참고 자료

- [MCP Python SDK (공식)](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP 문서 (gofastmcp.com)](https://gofastmcp.com/)
- [MCP 공식 사이트 - Build a Server](https://modelcontextprotocol.io/docs/develop/build-server)
- [Claude Code MCP 연동 문서](https://code.claude.com/docs/en/mcp)
- [MCP Transport 비교 (MCPcat)](https://mcpcat.io/guides/comparing-stdio-sse-streamablehttp/)
- [FastMCP 튜토리얼 (Firecrawl)](https://www.firecrawl.dev/blog/fastmcp-tutorial-building-mcp-servers-python)
- [FastMCP + DataCamp 가이드](https://www.datacamp.com/tutorial/building-mcp-server-client-fastmcp)

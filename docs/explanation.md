# TIL MCP 서버 — 전체 원리 설명

## 전체 그림

```
사용자: "Python 데코레이터 배운 거 기록해줘"
         │
         ▼
   ┌─────────────┐
   │ Claude Code  │  ← MCP 클라이언트
   │  (LLM)       │
   └──────┬──────┘
          │  stdin/stdout (JSON 메시지)
          ▼
   ┌─────────────┐
   │ server.py    │  ← MCP 서버 (우리가 만든 것)
   │  FastMCP     │
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │ SQLite DB    │  ← data/til.db
   └─────────────┘
```

Claude Code가 우리 서버를 **별도 프로세스**로 실행하고, **stdin/stdout**으로 JSON을 주고받는다. 이게 MCP의 stdio 전송 방식이다.

---

## 파일별 상세 설명

### 1. `requirements.txt` — 의존성

```
mcp>=1.26.0
```

딱 하나. `mcp` 패키지 안에 `FastMCP`가 내장되어 있어서 별도 설치 불필요.

---

### 2. `src/til_server/__init__.py` — 패키지 선언

```python
# TIL(Today I Learned) 지식 관리 MCP 서버
```

Python에게 "이 폴더는 패키지야"라고 알려주는 파일. 없으면 `from til_server import ...`가 안 된다.

---

### 3. `server.py` — 진입점 (모든 것의 시작)

```python
from mcp.server.fastmcp import FastMCP
from .db import init_db
from .tools import register_tools
from .resources import register_resources
from .prompts import register_prompts

mcp = FastMCP("TIL Server")    # ① 서버 인스턴스 생성
init_db()                       # ② DB 테이블 초기화
register_tools(mcp)             # ③ Tool 등록
register_resources(mcp)         # ④ Resource 등록
register_prompts(mcp)           # ⑤ Prompt 등록

if __name__ == "__main__":
    mcp.run()                   # ⑥ stdio 모드로 서버 시작
```

**원리**: `FastMCP("TIL Server")`가 서버 객체를 만들고, 각 모듈에서 데코레이터로 기능을 등록한 뒤, `mcp.run()`으로 stdin/stdout 리스닝을 시작한다.

`mcp.run()`이 호출되면:
- stdin에서 JSON-RPC 메시지를 읽음
- 요청에 맞는 tool/resource/prompt를 찾아서 실행
- 결과를 JSON-RPC로 stdout에 씀

---

### 4. `db.py` — SQLite 데이터베이스 (데이터 저장소)

**핵심 설정:**

```python
DB_PATH = Path(__file__).parent.parent.parent / "data" / "til.db"
```
`src/til_server/db.py` 기준으로 `../../data/til.db` = 프로젝트 루트의 `data/til.db`

```python
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row    # dict처럼 row["title"] 접근 가능
    conn.execute("PRAGMA journal_mode=WAL")   # 읽기/쓰기 동시성 향상
    conn.execute("PRAGMA foreign_keys=ON")    # 외래키 제약조건 활성화
    return conn
```

**테이블 3개:**

```sql
tils        ← TIL 본문 (id, title, content, category, created_at, updated_at)
tags        ← 태그 마스터 (id, name)  — "python", "mcp" 같은 태그 이름
til_tags    ← 다대다 연결 (til_id, tag_id)  — 하나의 TIL에 여러 태그 가능
```

**왜 태그를 별도 테이블로?**

TIL 1에 "python", TIL 2에도 "python" 태그를 달면, `tags` 테이블에 "python"은 하나만 존재하고 `til_tags`에서 각각 연결한다. 이걸 **다대다(Many-to-Many) 관계**라고 한다.

```
tils: [1, "Python 학습"]  ←──┐
                              ├── til_tags: (1, 1), (2, 1)
tils: [2, "Flask 학습"]   ←──┘        │
                                       ▼
                              tags: [1, "python"]
```

**주요 CRUD 함수들:**

```python
def create_til(title, content, category="general", tags=None) -> dict:
    # INSERT INTO tils → 태그 연결 → 결과 반환

def update_til(til_id, title=None, content=None, ...) -> dict:
    # 존재 확인 → 전달된 필드만 UPDATE → 태그 교체(있으면)

def delete_til(til_id) -> bool:
    # DELETE FROM tils → CASCADE로 til_tags도 자동 삭제

def search_tils(query, tag=None, category=None) -> list[dict]:
    # title LIKE '%query%' OR content LIKE '%query%' + 태그/카테고리 필터
```

**헬퍼 함수:**

```python
def _attach_tags(conn, til_id, tags):
    # 태그마다: INSERT OR IGNORE INTO tags → til_tags에 연결
    # OR IGNORE: 이미 있는 태그면 새로 만들지 않고 기존 것 사용

def _row_to_til(row, conn) -> dict:
    # sqlite3.Row → {"id": 1, "title": "...", "tags": ["python", "mcp"], ...}
    # 매번 해당 TIL의 태그도 함께 조회해서 dict에 포함
```

---

### 5. `tools.py` — Tool 6개 (데이터를 변경하는 기능)

```python
def register_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def create_til(title: str, content: str, tags: list[str] | None = None, category: str = "general") -> dict:
```

**`@mcp.tool()` 데코레이터가 하는 일:**

1. 함수 이름 `create_til` → tool 이름으로 등록
2. 타입 힌트 `title: str` → JSON Schema `{"type": "string"}` 자동 생성
3. docstring → Claude가 보는 tool 설명
4. `list[str] | None = None` → 선택적 파라미터로 등록

Claude가 이 정보를 보고 **스스로 판단**한다:
> "사용자가 '기록해줘'라고 했네 → create_til이 적합하겠다 → title과 content를 추출해서 호출하자"

**입력 검증 패턴:**

```python
if not title.strip():
    raise ValueError("제목은 비어있을 수 없습니다")
```

FastMCP가 타입은 자동으로 검증하지만 (str인지, int인지), "빈 문자열이면 안 됨" 같은 비즈니스 규칙은 직접 체크한다. `ValueError`를 raise하면 FastMCP가 자동으로 에러 응답으로 변환해서 Claude에게 보낸다.

**6개 Tool 요약:**

| Tool | 하는 일 | REST 비유 |
|------|---------|----------|
| `create_til` | TIL 생성 | POST |
| `update_til` | TIL 수정 (전달된 필드만) | PATCH |
| `delete_til` | TIL 삭제 | DELETE |
| `search_til` | 키워드 검색 | POST (검색) |
| `add_tag` | 태그 추가 | PATCH |
| `export_til` | Markdown으로 변환 | POST |

`export_til`이 재밌는 부분:
```python
lines = ["# TIL Export\n"]
for til in tils:
    lines.append(f"## {til['title']}")
    lines.append(f"- **카테고리**: {til['category']}")
    ...
markdown = "\n".join(lines)
return {"status": "exported", "markdown": markdown, "count": len(tils)}
```
DB 데이터를 Markdown 문자열로 변환해서 반환한다.

---

### 6. `resources.py` — Resource 7개 (읽기 전용 조회)

```python
@mcp.resource("til://list")
def list_tils() -> str:
    tils = db.list_all_tils()
    return json.dumps(tils, ensure_ascii=False, indent=2)
```

**Tool과 Resource의 차이:**
- Tool: Claude가 "행동"할 때 호출. DB가 변경될 수 있음
- Resource: Claude가 "현재 상태를 확인"할 때 호출. 읽기만 함

**URI 스킴:**

`til://list`, `til://stats` 같은 커스텀 URI를 사용한다. 웹 URL(`https://`)처럼 고유 주소 역할이다.

**Resource Template:**
```python
@mcp.resource("til://{til_id}")
def get_til_detail(til_id: str) -> str:
```
`{til_id}` 부분이 동적 파라미터다. `til://42`로 요청하면 `til_id="42"`가 전달된다. REST API의 `/tils/:id`와 같은 개념이다.

**모든 Resource는 JSON 문자열을 반환:**
```python
return json.dumps(tils, ensure_ascii=False, indent=2)
```
`ensure_ascii=False`: 한글이 `\uXXXX`로 깨지지 않게.

---

### 7. `prompts.py` — Prompt 4개 (LLM 지시 템플릿)

```python
@mcp.prompt()
def write_til(topic: str) -> str:
    return f"""다음 주제에 대한 TIL을 작성해주세요.
주제: {topic}
작성 가이드:
1. 제목은 명확하고 간결하게
2. 핵심 내용을 3~5문장으로 요약
...
작성 후 create_til 도구를 사용하여 저장해주세요."""
```

**Prompt는 코드가 아니라 "텍스트 템플릿"이다.**

Claude에게 "이렇게 생각해"라는 지시를 미리 만들어두는 것이다. `write_til(topic="Python 데코레이터")`를 호출하면 위 템플릿에 주제가 채워진 텍스트가 Claude에게 전달되고, Claude는 그 지시대로 TIL을 작성한 뒤 `create_til` tool을 호출해서 저장한다.

**`weekly_review`가 특이한 점:**
```python
@mcp.prompt()
def weekly_review(week: str | None = None) -> str:
    tils = db.list_week_tils()  # ← 실제 DB에서 이번 주 데이터를 가져옴
    til_summary = json.dumps(tils, ...)
    return f"""이번 주 TIL들을 분석하여 회고를 작성해주세요.
이번 주 TIL 데이터:
{til_summary}
..."""
```
프롬프트 안에 **실제 데이터를 포함**시킨다. Claude가 이 프롬프트를 받으면 실제 이번 주 TIL 목록을 보면서 회고를 작성할 수 있다.

---

### 8. `tests/test_server.py` — 78개 테스트

**테스트 격리 패턴:**
```python
@pytest.fixture(autouse=True)
def test_db(tmp_path):
    test_db_path = tmp_path / "test_til.db"
    with mock.patch("til_server.db.DB_PATH", test_db_path):
        from til_server.db import init_db
        init_db()
        yield test_db_path
```
`autouse=True`: 모든 테스트에 자동 적용. `mock.patch`로 DB 경로를 임시 디렉토리로 바꿔서 실제 `data/til.db`에 영향 없이 테스트한다. 각 테스트마다 새 DB를 만들어서 테스트 간 간섭이 없다.

**FastMCP에 등록된 함수를 꺼내서 직접 테스트:**
```python
def _get_tool_fn(self, mcp_instance, name):
    tool = mcp_instance._tool_manager._tools.get(name)
    return tool.fn  # 데코레이터로 등록된 원본 함수
```
`@mcp.tool()`로 등록한 함수를 FastMCP 내부 매니저에서 꺼내서 직접 호출하는 방식이다.

---

### 9. Claude Code 연동 방법

```bash
claude mcp add --transport stdio til-server -- \
  /Users/ram/programming/vibecoding/mcp/venv/bin/python \
  -m src.til_server.server
```

이 명령이 하는 일:
1. Claude Code에 `til-server`라는 MCP 서버를 등록
2. `--transport stdio`: stdin/stdout으로 통신
3. `--` 뒤: 실행할 명령어 (venv의 python으로 서버 실행)

등록하면 Claude Code가 서버를 자동으로 실행하고, 사용자가 자연어로 말하면 적절한 tool/resource/prompt를 호출한다.

---

## 한 줄 정리

```
MCP = 규격 (프로토콜)
FastMCP = 그 규격에 맞는 서버를 쉽게 만들어주는 프레임워크
@mcp.tool() = "이 함수는 행동이야" 등록
@mcp.resource() = "이 함수는 조회야" 등록
@mcp.prompt() = "이 텍스트는 지시 템플릿이야" 등록
mcp.run() = stdin/stdout 열고 대기
SQLite = 데이터 저장
```

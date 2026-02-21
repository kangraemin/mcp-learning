# TIL MCP 서버 테스트 리포트

- **테스트 일시**: 2026-02-21
- **Python 버전**: 3.14.2
- **MCP SDK 버전**: 1.26.0
- **테스트 프레임워크**: pytest 9.0.2
- **테스트 파일**: `tests/test_server.py`

## 테스트 결과 요약

| 구분 | 테스트 수 | 통과 | 실패 | 비고 |
|------|-----------|------|------|------|
| 서버 시작 | 7 | 7 | 0 | 모듈 임포트, FastMCP 인스턴스, DB 초기화 |
| DB CRUD | 18 | 18 | 0 | create, read, update, delete, search, add_tag |
| DB Resource 조회 | 12 | 12 | 0 | list, today, week, tags, categories, stats, export |
| Tool 함수 | 15 | 15 | 0 | 6개 tool의 정상/에러 케이스 |
| Resource 함수 | 10 | 10 | 0 | 7개 resource + 데이터 포함 검증 |
| Prompt 함수 | 7 | 7 | 0 | 4개 prompt + 파라미터 변형 |
| 엣지 케이스 | 11 | 11 | 0 | 특수문자, 유니코드, CASCADE 삭제 등 |
| **합계** | **78** | **78** | **0** | **전체 통과 (0.69초)** |

## 세부 테스트 항목

### 1. 서버 정상 실행 테스트 (7건)

모든 모듈이 문법 오류 없이 임포트되고, FastMCP 인스턴스가 정상 생성되는지 확인.

- `server.py`, `db.py`, `tools.py`, `resources.py`, `prompts.py` 임포트 성공
- `FastMCP("TIL Server")` 인스턴스 생성 확인 (이름: "TIL Server")
- `init_db()` 호출 시 `tils`, `tags`, `til_tags` 테이블 생성 확인

### 2. DB CRUD 테스트 (18건)

`db.py`의 각 함수를 직접 호출하여 데이터 정합성 확인.

| 함수 | 테스트 내용 | 결과 |
|------|-------------|------|
| `create_til` | 기본 생성, 태그 포함, 카테고리 지정 | PASS |
| `get_til_by_id` | 정상 조회, 미존재 ID (None 반환) | PASS |
| `update_til` | 제목 수정, 내용 수정, 태그 교체, 미존재 ID (LookupError) | PASS |
| `delete_til` | 정상 삭제 (True), 미존재 ID (False) | PASS |
| `search_tils` | 제목 검색, 내용 검색, 태그 필터, 카테고리 필터 | PASS |
| `add_tag` | 태그 추가, 미존재 ID (LookupError), 중복 태그 방지 | PASS |

### 3. Resource 조회 함수 테스트 (12건)

Resource에서 사용하는 `db.py` 조회 함수들의 동작 검증.

- `list_all_tils`: 빈 목록, 데이터 포함 목록
- `list_today_tils`: 오늘 생성된 데이터 조회
- `list_week_tils`: 이번 주 데이터 조회
- `list_all_tags`: 빈 목록, 태그 개수 정확성
- `list_all_categories`: 카테고리별 분류
- `get_stats`: 빈 상태, 데이터 포함 통계 (total, today, top_tags)
- `get_tils_for_export`: ID 지정, 날짜 범위, 미존재 ID

### 4. Tool 함수 테스트 (15건)

`tools.py`의 6개 tool을 FastMCP 인스턴스에서 꺼내어 직접 호출.

| Tool | 정상 케이스 | 에러 케이스 |
|------|-------------|-------------|
| `create_til` | 생성 성공, 태그 포함 | 빈 제목 (ValueError), 빈 내용 (ValueError) |
| `update_til` | 수정 성공 | 빈 제목 (ValueError) |
| `delete_til` | 삭제 성공 | 미존재 ID (LookupError) |
| `search_til` | 검색 성공 | 빈 검색어 (ValueError) |
| `add_tag` | 태그 추가 성공 | 빈 태그 (ValueError) |
| `export_til` | ID 지정 내보내기, Markdown 형식 확인 | 파라미터 없음 (ValueError), 결과 없음 (empty) |

### 5. Resource 함수 테스트 (10건)

`resources.py`의 7개 resource를 FastMCP 인스턴스에서 꺼내어 JSON 파싱 검증.

- `til://list` → 빈 리스트/데이터 포함 리스트 (JSON 배열)
- `til://list/today` → JSON 배열
- `til://list/week` → JSON 배열
- `til://{til_id}` → Resource Template 등록 확인 + 상세 조회
- `til://tags` → JSON 배열
- `til://categories` → JSON 배열
- `til://stats` → JSON 객체 (total, today, this_week 키 포함)

### 6. Prompt 함수 테스트 (7건)

`prompts.py`의 4개 prompt의 반환 문자열 검증.

| Prompt | 테스트 내용 | 결과 |
|--------|-------------|------|
| `write_til` | topic 파라미터 포함, "create_til" 안내 포함 | PASS |
| `weekly_review` | 기본 (이번 주), 주차 지정 ("2주차") | PASS |
| `suggest_topics` | 기본, 카테고리 지정 ("backend") | PASS |
| `summarize_learnings` | 날짜 범위 포함 확인 | PASS |

### 7. 엣지 케이스 테스트 (11건)

| 테스트 | 설명 | 결과 |
|--------|------|------|
| 태그 정규화 | "Python" → "python", "UPPER" → "upper" | PASS |
| 태그 공백 제거 | "  python  " → "python" | PASS |
| 빈 태그 무시 | ["python", "", "  "] → ["python"] | PASS |
| CASCADE 삭제 | TIL 삭제 시 til_tags 레코드도 삭제 | PASS |
| 공유 태그 | 여러 TIL이 같은 태그 공유, count 정확 | PASS |
| 빈 업데이트 | 필드 미변경 update 호출 | PASS |
| 검색 결과 없음 | 매칭 없는 키워드 검색 → 빈 리스트 | PASS |
| 특수문자 | SQL injection 시도 문자열 저장/조회 | PASS |
| 유니코드 | 한글 제목/내용 저장/조회 | PASS |
| Export Markdown | 마크다운 포맷 (# 헤더, ** 볼드 등) 검증 | PASS |

## 발견된 문제점

**없음.** 모든 78개 테스트가 통과했으며, 코드에서 버그를 발견하지 못했다.

## 코드 품질 평가

| 항목 | 평가 |
|------|------|
| 입력 검증 | 빈 문자열, 미존재 ID 등 적절한 에러 핸들링 |
| 데이터 정합성 | 외래 키, CASCADE 삭제, 중복 방지 정상 동작 |
| 태그 정규화 | 소문자 변환, 공백 트리밍, 빈 태그 무시 |
| SQL 안전성 | 파라미터 바인딩(?) 사용, SQL injection 방어 |
| 유니코드 지원 | 한글 등 유니코드 문자 정상 처리 |
| Markdown Export | 구조화된 Markdown 포맷 출력 정상 |

## 테스트 환경 참고사항

- 각 테스트는 `tmp_path` (임시 디렉토리)에 별도 SQLite DB를 생성하여 격리 실행
- `unittest.mock.patch`로 `DB_PATH`를 테스트용 경로로 교체
- 기존 `data/til.db`에 영향 없음

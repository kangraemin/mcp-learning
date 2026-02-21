"""
db.py - SQLite 데이터베이스 관리 모듈

MCP 원리 설명:
    MCP 서버는 데이터를 영속적으로 저장해야 한다.
    이 모듈은 SQLite를 사용하여 TIL 데이터를 로컬 파일에 저장한다.
    동기 sqlite3를 사용하는 이유: stdio 전송 방식에서 단일 클라이언트만 접속하므로
    비동기(aiosqlite)가 불필요하며, 코드가 훨씬 간단해진다.
"""
import sqlite3
from pathlib import Path

# DB 파일 경로: 프로젝트 루트의 data/til.db
DB_PATH = Path(__file__).parent.parent.parent / "data" / "til.db"


def get_connection() -> sqlite3.Connection:
    """SQLite 연결을 생성하고 반환한다.

    Row 팩토리를 설정하여 딕셔너리처럼 컬럼명으로 접근 가능하게 한다.
    WAL 모드를 사용하여 읽기/쓰기 동시성을 높인다.
    외래 키 제약 조건을 활성화한다.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """데이터베이스 테이블을 초기화한다.

    IF NOT EXISTS를 사용하여 이미 테이블이 있으면 건너뛴다.
    서버 시작 시 자동으로 호출된다.
    """
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tils (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS til_tags (
                til_id INTEGER REFERENCES tils(id) ON DELETE CASCADE,
                tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (til_id, tag_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


# --- TIL CRUD 함수 ---

def create_til(title: str, content: str, category: str = "general",
               tags: list[str] | None = None) -> dict:
    """새 TIL 항목을 DB에 저장한다."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO tils (title, content, category) VALUES (?, ?, ?)",
            (title, content, category),
        )
        til_id = cursor.lastrowid

        # 태그가 있으면 연결
        if tags:
            _attach_tags(conn, til_id, tags)

        conn.commit()
        return get_til_by_id(til_id, conn=conn)
    finally:
        conn.close()


def update_til(til_id: int, title: str | None = None,
               content: str | None = None, category: str | None = None,
               tags: list[str] | None = None) -> dict:
    """기존 TIL을 수정한다. 전달된 필드만 업데이트한다."""
    conn = get_connection()
    try:
        # 존재 확인
        existing = get_til_by_id(til_id, conn=conn)
        if not existing:
            raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")

        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if category is not None:
            updates.append("category = ?")
            params.append(category)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(til_id)
            conn.execute(
                f"UPDATE tils SET {', '.join(updates)} WHERE id = ?",
                params,
            )

        # 태그가 명시적으로 전달되면 교체
        if tags is not None:
            conn.execute("DELETE FROM til_tags WHERE til_id = ?", (til_id,))
            _attach_tags(conn, til_id, tags)

        conn.commit()
        return get_til_by_id(til_id, conn=conn)
    finally:
        conn.close()


def delete_til(til_id: int) -> bool:
    """TIL을 삭제한다. 삭제 성공 여부를 반환한다."""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM tils WHERE id = ?", (til_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def search_tils(query: str, tag: str | None = None,
                category: str | None = None) -> list[dict]:
    """키워드로 TIL을 검색한다. 제목과 내용에서 LIKE 검색을 수행한다."""
    conn = get_connection()
    try:
        sql = """
            SELECT DISTINCT t.id, t.title, t.content, t.category,
                   t.created_at, t.updated_at
            FROM tils t
            LEFT JOIN til_tags tt ON t.id = tt.til_id
            LEFT JOIN tags tg ON tt.tag_id = tg.id
            WHERE (t.title LIKE ? OR t.content LIKE ?)
        """
        params: list = [f"%{query}%", f"%{query}%"]

        if tag:
            sql += " AND tg.name = ?"
            params.append(tag)
        if category:
            sql += " AND t.category = ?"
            params.append(category)

        sql += " ORDER BY t.created_at DESC"

        rows = conn.execute(sql, params).fetchall()
        return [_row_to_til(row, conn) for row in rows]
    finally:
        conn.close()


def add_tag(til_id: int, tag: str) -> dict:
    """TIL에 단일 태그를 추가한다."""
    conn = get_connection()
    try:
        existing = get_til_by_id(til_id, conn=conn)
        if not existing:
            raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")

        _attach_tags(conn, til_id, [tag])
        conn.commit()
        return get_til_by_id(til_id, conn=conn)
    finally:
        conn.close()


def get_til_by_id(til_id: int, conn: sqlite3.Connection | None = None) -> dict | None:
    """ID로 TIL을 조회한다."""
    should_close = conn is None
    if conn is None:
        conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tils WHERE id = ?", (til_id,)).fetchone()
        if not row:
            return None
        return _row_to_til(row, conn)
    finally:
        if should_close:
            conn.close()


# --- Resource용 조회 함수 ---

def list_all_tils() -> list[dict]:
    """전체 TIL 목록을 최근순으로 반환한다."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tils ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_til(row, conn) for row in rows]
    finally:
        conn.close()


def list_today_tils() -> list[dict]:
    """오늘 작성된 TIL 목록을 반환한다."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tils WHERE date(created_at) = date('now') ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_til(row, conn) for row in rows]
    finally:
        conn.close()


def list_week_tils() -> list[dict]:
    """이번 주(월~일) 작성된 TIL 목록을 반환한다."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tils WHERE date(created_at) >= date('now', 'weekday 0', '-6 days') ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_til(row, conn) for row in rows]
    finally:
        conn.close()


def list_all_tags() -> list[dict]:
    """전체 태그 목록과 사용 횟수를 반환한다."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT tg.name, COUNT(tt.til_id) as count
            FROM tags tg
            LEFT JOIN til_tags tt ON tg.id = tt.tag_id
            GROUP BY tg.id
            ORDER BY count DESC
        """).fetchall()
        return [{"name": row["name"], "count": row["count"]} for row in rows]
    finally:
        conn.close()


def list_all_categories() -> list[dict]:
    """전체 카테고리 목록과 TIL 개수를 반환한다."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT category, COUNT(*) as count
            FROM tils
            GROUP BY category
            ORDER BY count DESC
        """).fetchall()
        return [{"category": row["category"], "count": row["count"]} for row in rows]
    finally:
        conn.close()


def get_stats() -> dict:
    """학습 통계를 반환한다."""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) as cnt FROM tils").fetchone()["cnt"]
        today = conn.execute(
            "SELECT COUNT(*) as cnt FROM tils WHERE date(created_at) = date('now')"
        ).fetchone()["cnt"]
        this_week = conn.execute(
            "SELECT COUNT(*) as cnt FROM tils WHERE date(created_at) >= date('now', 'weekday 0', '-6 days')"
        ).fetchone()["cnt"]

        # 인기 태그 상위 5개
        top_tags = conn.execute("""
            SELECT tg.name, COUNT(tt.til_id) as count
            FROM tags tg
            JOIN til_tags tt ON tg.id = tt.tag_id
            GROUP BY tg.id
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()

        # 카테고리별 분포
        categories = conn.execute("""
            SELECT category, COUNT(*) as count
            FROM tils GROUP BY category ORDER BY count DESC
        """).fetchall()

        # 최근 7일 일별 추이
        daily = conn.execute("""
            SELECT date(created_at) as day, COUNT(*) as count
            FROM tils
            WHERE date(created_at) >= date('now', '-6 days')
            GROUP BY date(created_at)
            ORDER BY day
        """).fetchall()

        return {
            "total": total,
            "today": today,
            "this_week": this_week,
            "top_tags": [{"name": r["name"], "count": r["count"]} for r in top_tags],
            "categories": [{"category": r["category"], "count": r["count"]} for r in categories],
            "daily_trend": [{"date": r["day"], "count": r["count"]} for r in daily],
        }
    finally:
        conn.close()


def get_tils_for_export(til_id: int | None = None,
                        date_from: str | None = None,
                        date_to: str | None = None) -> list[dict]:
    """내보내기용 TIL 데이터를 조회한다."""
    conn = get_connection()
    try:
        if til_id is not None:
            til = get_til_by_id(til_id, conn=conn)
            return [til] if til else []

        sql = "SELECT * FROM tils WHERE 1=1"
        params: list = []
        if date_from:
            sql += " AND date(created_at) >= date(?)"
            params.append(date_from)
        if date_to:
            sql += " AND date(created_at) <= date(?)"
            params.append(date_to)
        sql += " ORDER BY created_at DESC"

        rows = conn.execute(sql, params).fetchall()
        return [_row_to_til(row, conn) for row in rows]
    finally:
        conn.close()


def get_tils_by_date_range(date_from: str, date_to: str) -> list[dict]:
    """특정 기간의 TIL을 조회한다. Prompt에서 사용."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tils WHERE date(created_at) BETWEEN date(?) AND date(?) ORDER BY created_at DESC",
            (date_from, date_to),
        ).fetchall()
        return [_row_to_til(row, conn) for row in rows]
    finally:
        conn.close()


# --- 내부 헬퍼 함수 ---

def _attach_tags(conn: sqlite3.Connection, til_id: int, tags: list[str]) -> None:
    """TIL에 태그를 연결한다. 태그가 없으면 새로 생성한다."""
    for tag_name in tags:
        tag_name = tag_name.strip().lower()
        if not tag_name:
            continue
        # INSERT OR IGNORE: 이미 있는 태그면 무시
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
        # 중복 연결 방지
        conn.execute(
            "INSERT OR IGNORE INTO til_tags (til_id, tag_id) VALUES (?, ?)",
            (til_id, tag_row["id"]),
        )


def _get_tags_for_til(til_id: int, conn: sqlite3.Connection) -> list[str]:
    """특정 TIL에 연결된 태그 이름 목록을 반환한다."""
    rows = conn.execute("""
        SELECT tg.name FROM tags tg
        JOIN til_tags tt ON tg.id = tt.tag_id
        WHERE tt.til_id = ?
        ORDER BY tg.name
    """, (til_id,)).fetchall()
    return [row["name"] for row in rows]


def _row_to_til(row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
    """sqlite3.Row를 태그를 포함한 딕셔너리로 변환한다."""
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "category": row["category"],
        "tags": _get_tags_for_til(row["id"], conn),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

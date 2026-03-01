"""
notion_storage.py - Notion API 기반 TIL 저장소 모듈

Notion 데이터베이스에 TIL을 페이지로 저장한다.
각 페이지의 properties로 메타데이터를, body blocks로 content를 관리한다.

필수 Notion DB 속성:
    - Name (title): TIL 제목
    - ID (number): TIL 고유 ID (YYYYMMDDHHMMSS)
    - Category (select): 카테고리
    - Tags (multi_select): 태그 목록
    - Created At (date): 원본 생성일
    - Updated At (date): 수정일
"""
from __future__ import annotations

import os
from datetime import datetime, date, timedelta

try:
    from notion_client import Client as NotionClient
except ImportError:
    raise ImportError(
        "Notion 백엔드를 사용하려면 notion-client를 설치하세요:\n"
        "  pip install 'til-server[notion]'\n"
        "  또는: pip install notion-client"
    )

from .config import get_backend_config


class NotionStorageError(Exception):
    pass


# --- 인증 & 설정 ---

_client_cache: NotionClient | None = None
_db_id_cache: str | None = None


def _get_token() -> str:
    """Notion API 토큰을 환경변수 또는 config에서 가져온다."""
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if token:
        return token
    config = get_backend_config()
    token = config.get("token", "").strip()
    if token:
        return token
    raise NotionStorageError(
        "Notion 인증이 필요합니다.\n"
        "방법 1: NOTION_TOKEN 환경변수 설정\n"
        "방법 2: ~/.til/config.json의 notion.token에 토큰 입력"
    )


def _get_database_id() -> str:
    """Notion 데이터베이스 ID를 환경변수 또는 config에서 가져온다."""
    db_id = os.environ.get("NOTION_DATABASE_ID", "").strip()
    if db_id:
        return db_id
    config = get_backend_config()
    db_id = config.get("database_id", "").strip()
    if db_id:
        return db_id
    raise NotionStorageError(
        "Notion 데이터베이스 ID가 필요합니다.\n"
        "방법 1: NOTION_DATABASE_ID 환경변수 설정\n"
        "방법 2: ~/.til/config.json의 notion.database_id에 ID 입력"
    )


def _client() -> NotionClient:
    """Notion 클라이언트 인스턴스를 반환한다."""
    global _client_cache
    if _client_cache is None:
        _client_cache = NotionClient(auth=_get_token())
    return _client_cache


def _db_id() -> str:
    """데이터베이스 ID를 캐싱하여 반환한다."""
    global _db_id_cache
    if _db_id_cache is None:
        _db_id_cache = _get_database_id()
    return _db_id_cache


# --- 초기화 ---

def _ensure_dir() -> None:
    """Notion DB가 존재하는지 확인한다. API로 DB를 생성하지 않는다."""
    try:
        _client().databases.retrieve(database_id=_db_id())
    except Exception as e:
        raise NotionStorageError(
            f"Notion 데이터베이스에 접근할 수 없습니다: {e}\n"
            "Notion에서 직접 데이터베이스를 생성한 후, "
            "다음 속성을 추가해주세요:\n"
            "  - Name (title): TIL 제목\n"
            "  - ID (number): TIL 고유 ID\n"
            "  - Category (select): 카테고리\n"
            "  - Tags (multi_select): 태그 목록\n"
            "  - Created At (date): 생성일\n"
            "  - Updated At (date): 수정일"
        ) from e


# --- Notion ↔ TIL 변환 ---

def _page_to_til(page: dict, content: str | None = None) -> dict:
    """Notion 페이지를 TIL dict로 변환한다."""
    props = page.get("properties", {})

    # title
    title_prop = props.get("Name", {})
    title_arr = title_prop.get("title", [])
    title = title_arr[0]["plain_text"] if title_arr else ""

    # id
    id_prop = props.get("ID", {})
    til_id = int(id_prop.get("number", 0)) if id_prop.get("number") else 0

    # category
    cat_prop = props.get("Category", {})
    cat_select = cat_prop.get("select")
    category = cat_select["name"] if cat_select else "general"

    # tags
    tags_prop = props.get("Tags", {})
    tags = [t["name"] for t in tags_prop.get("multi_select", [])]

    # created_at
    created_prop = props.get("Created At", {})
    created_date = created_prop.get("date")
    created_at = created_date["start"] if created_date else ""

    # updated_at
    updated_prop = props.get("Updated At", {})
    updated_date = updated_prop.get("date")
    updated_at = updated_date["start"] if updated_date else ""

    if content is None:
        content = _get_page_content(page["id"])

    return {
        "id": til_id,
        "title": title,
        "content": content,
        "category": category,
        "tags": tags,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _til_to_properties(til_id: int, title: str, category: str,
                        tags: list[str], created_at: str,
                        updated_at: str) -> dict:
    """TIL 메타데이터를 Notion page properties로 변환한다."""
    props: dict = {
        "Name": {"title": [{"text": {"content": title}}]},
        "ID": {"number": til_id},
        "Category": {"select": {"name": category}},
        "Tags": {"multi_select": [{"name": t} for t in tags]},
    }
    if created_at:
        props["Created At"] = {"date": {"start": created_at}}
    if updated_at:
        props["Updated At"] = {"date": {"start": updated_at}}
    return props


def _markdown_to_blocks(content: str) -> list[dict]:
    """Markdown 텍스트를 Notion blocks으로 변환한다.

    간단한 변환: 각 줄을 paragraph block으로 생성한다.
    코드 블록(```...```)은 code block으로 변환한다.
    """
    blocks: list[dict] = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # 코드 블록 처리
        if line.strip().startswith("```"):
            lang = line.strip().removeprefix("```").strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # 닫는 ``` 건너뜀

            code_text = "\n".join(code_lines)
            if code_text:
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code_text}}],
                        "language": lang,
                    },
                })
            continue

        # 빈 줄 건너뜀
        if not line.strip():
            i += 1
            continue

        # 일반 텍스트 → paragraph
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": line}}],
            },
        })
        i += 1

    return blocks


def _blocks_to_markdown(blocks: list[dict]) -> str:
    """Notion blocks를 Markdown 텍스트로 변환한다."""
    lines: list[str] = []

    for block in blocks:
        block_type = block.get("type", "")

        if block_type == "paragraph":
            rich_text = block.get("paragraph", {}).get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            lines.append(text)

        elif block_type == "code":
            code_data = block.get("code", {})
            rich_text = code_data.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            lang = code_data.get("language", "")
            lines.append(f"```{lang}")
            lines.append(text)
            lines.append("```")

        elif block_type in ("heading_1", "heading_2", "heading_3"):
            rich_text = block.get(block_type, {}).get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            level = int(block_type[-1])
            lines.append(f"{'#' * level} {text}")

        elif block_type == "bulleted_list_item":
            rich_text = block.get("bulleted_list_item", {}).get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            lines.append(f"- {text}")

        elif block_type == "numbered_list_item":
            rich_text = block.get("numbered_list_item", {}).get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            lines.append(f"1. {text}")

    return "\n".join(lines)


def _get_page_content(page_id: str) -> str:
    """페이지의 body blocks를 읽어 Markdown으로 반환한다."""
    blocks_resp = _client().blocks.children.list(block_id=page_id)
    blocks = blocks_resp.get("results", [])
    return _blocks_to_markdown(blocks)


# --- Notion 쿼리 헬퍼 ---

def _query_all_pages(**kwargs) -> list[dict]:
    """페이지네이션을 처리하여 모든 페이지를 반환한다."""
    pages: list[dict] = []
    has_more = True
    start_cursor = None

    while has_more:
        resp = _client().databases.query(
            database_id=_db_id(),
            start_cursor=start_cursor,
            **kwargs,
        )
        pages.extend(resp.get("results", []))
        has_more = resp.get("has_more", False)
        start_cursor = resp.get("next_cursor")

    return pages


def _find_page_by_id(til_id: int) -> dict | None:
    """ID property로 페이지를 찾는다."""
    resp = _client().databases.query(
        database_id=_db_id(),
        filter={"property": "ID", "number": {"equals": til_id}},
    )
    results = resp.get("results", [])
    return results[0] if results else None


# --- TIL CRUD 함수 ---

def create_til(title: str, content: str, category: str = "general",
               tags: list[str] | None = None) -> dict:
    """새 TIL을 Notion 페이지로 생성한다."""
    now = datetime.now()
    til_id = int(now.strftime("%Y%m%d%H%M%S"))
    now_str = now.isoformat()
    tag_list = [t.strip().lower() for t in (tags or []) if t.strip()]

    properties = _til_to_properties(til_id, title, category, tag_list, now_str, now_str)
    children = _markdown_to_blocks(content)

    page = _client().pages.create(
        parent={"database_id": _db_id()},
        properties=properties,
        children=children,
    )

    return _page_to_til(page, content=content)


def _create_til_with_metadata(til_id: int, title: str, content: str,
                               category: str, tags: list[str],
                               created_at: str, updated_at: str) -> dict:
    """마이그레이션용: 메타데이터를 보존하여 TIL을 생성한다."""
    properties = _til_to_properties(til_id, title, category, tags, created_at, updated_at)
    children = _markdown_to_blocks(content)

    page = _client().pages.create(
        parent={"database_id": _db_id()},
        properties=properties,
        children=children,
    )

    return _page_to_til(page, content=content)


def update_til(til_id: int, title: str | None = None,
               content: str | None = None, category: str | None = None,
               tags: list[str] | None = None) -> dict:
    """기존 TIL을 수정한다."""
    page = _find_page_by_id(til_id)
    if not page:
        raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")

    existing = _page_to_til(page)
    new_title = title if title is not None else existing["title"]
    new_category = category if category is not None else existing["category"]
    new_tags = (
        [t.strip().lower() for t in tags if t.strip()]
        if tags is not None
        else existing["tags"]
    )
    updated_at = datetime.now().isoformat()

    properties = _til_to_properties(
        til_id, new_title, new_category, new_tags,
        existing["created_at"], updated_at,
    )

    _client().pages.update(page_id=page["id"], properties=properties)

    # content 업데이트: 기존 blocks 삭제 후 새로 추가
    if content is not None:
        # 기존 blocks 삭제
        blocks_resp = _client().blocks.children.list(block_id=page["id"])
        for block in blocks_resp.get("results", []):
            _client().blocks.delete(block_id=block["id"])

        # 새 blocks 추가
        new_blocks = _markdown_to_blocks(content)
        if new_blocks:
            _client().blocks.children.append(
                block_id=page["id"], children=new_blocks,
            )

    final_content = content if content is not None else existing["content"]
    return {
        "id": til_id,
        "title": new_title,
        "content": final_content,
        "category": new_category,
        "tags": new_tags,
        "created_at": existing["created_at"],
        "updated_at": updated_at,
    }


def delete_til(til_id: int) -> bool:
    """TIL(페이지)을 아카이브한다."""
    page = _find_page_by_id(til_id)
    if not page:
        return False
    _client().pages.update(page_id=page["id"], archived=True)
    return True


def search_tils(query: str, tag: str | None = None,
                category: str | None = None) -> list[dict]:
    """키워드로 TIL을 검색한다."""
    filters: list[dict] = []

    if tag:
        filters.append({
            "property": "Tags",
            "multi_select": {"contains": tag.lower()},
        })
    if category:
        filters.append({
            "property": "Category",
            "select": {"equals": category},
        })

    kwargs: dict = {}
    if filters:
        if len(filters) == 1:
            kwargs["filter"] = filters[0]
        else:
            kwargs["filter"] = {"and": filters}

    pages = _query_all_pages(
        sorts=[{"property": "ID", "direction": "descending"}],
        **kwargs,
    )

    results = []
    query_lower = query.lower()
    for page in pages:
        til = _page_to_til(page)
        if (query_lower not in til["title"].lower()
                and query_lower not in til["content"].lower()):
            continue
        results.append(til)

    return results


def add_tag(til_id: int, tag: str) -> dict:
    """TIL에 태그를 추가한다."""
    page = _find_page_by_id(til_id)
    if not page:
        raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")

    existing = _page_to_til(page)
    tag_clean = tag.strip().lower()
    if tag_clean and tag_clean not in existing["tags"]:
        return update_til(til_id, tags=existing["tags"] + [tag_clean])
    return existing


def get_til_by_id(til_id: int) -> dict | None:
    """ID로 TIL을 조회한다."""
    page = _find_page_by_id(til_id)
    return _page_to_til(page) if page else None


# --- Resource용 조회 함수 ---

def list_all_tils() -> list[dict]:
    """전체 TIL을 최근순으로 반환한다."""
    pages = _query_all_pages(
        sorts=[{"property": "ID", "direction": "descending"}],
    )
    return [_page_to_til(p) for p in pages]


def list_today_tils() -> list[dict]:
    """오늘 작성된 TIL을 반환한다."""
    today = date.today().isoformat()
    return [t for t in list_all_tils() if t["created_at"][:10] == today]


def list_week_tils() -> list[dict]:
    """최근 7일간 작성된 TIL을 반환한다."""
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=6)).isoformat()
    return [t for t in list_all_tils()
            if week_ago <= t["created_at"][:10] <= today]


def get_stats() -> dict:
    """학습 통계를 반환한다."""
    all_tils = list_all_tils()
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=6)).isoformat()

    today_count = sum(1 for t in all_tils if t["created_at"][:10] == today)
    week_count = sum(1 for t in all_tils
                     if week_ago <= t["created_at"][:10] <= today)

    tag_counts: dict[str, int] = {}
    for t in all_tils:
        for tg in t["tags"]:
            tag_counts[tg] = tag_counts.get(tg, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    cat_counts: dict[str, int] = {}
    for t in all_tils:
        cat = t["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    daily: dict[str, int] = {}
    for t in all_tils:
        day = t["created_at"][:10]
        if week_ago <= day <= today:
            daily[day] = daily.get(day, 0) + 1

    return {
        "total": len(all_tils),
        "today": today_count,
        "this_week": week_count,
        "top_tags": [{"name": n, "count": c} for n, c in top_tags],
        "categories": [
            {"category": cat, "count": cnt}
            for cat, cnt in sorted(cat_counts.items(),
                                   key=lambda x: x[1], reverse=True)
        ],
        "daily_trend": [
            {"date": d, "count": c} for d, c in sorted(daily.items())
        ],
    }


def get_tils_for_export(til_id: int | None = None,
                        date_from: str | None = None,
                        date_to: str | None = None) -> list[dict]:
    """내보내기용 TIL 데이터를 조회한다."""
    if til_id is not None:
        til = get_til_by_id(til_id)
        return [til] if til else []

    result = []
    for t in list_all_tils():
        day = t["created_at"][:10]
        if date_from and day < date_from:
            continue
        if date_to and day > date_to:
            continue
        result.append(t)
    return result


def get_tils_by_date_range(date_from: str, date_to: str) -> list[dict]:
    """특정 기간의 TIL을 조회한다."""
    return get_tils_for_export(date_from=date_from, date_to=date_to)


def get_tags() -> list[str]:
    """전체 태그 목록을 알파벳순으로 반환한다."""
    tag_set: set[str] = set()
    for t in list_all_tils():
        for tg in t["tags"]:
            tag_set.add(tg)
    return sorted(tag_set)


def get_categories() -> list[str]:
    """전체 카테고리 목록을 반환한다."""
    cat_set: set[str] = set()
    for t in list_all_tils():
        cat_set.add(t["category"])
    return sorted(cat_set)

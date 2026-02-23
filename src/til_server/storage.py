"""
storage.py - 파일 기반 TIL 저장소 모듈

SQLite 대신 로컬 마크다운 파일로 TIL을 저장/조회한다.
파일 경로: data/tils/YYYY-MM-DD-{slug}.md

파일 구조:
    ---
    id: 20260223143000
    title: 제목
    category: general
    tags: [tag1, tag2]
    created_at: 2026-02-23T14:30:00
    updated_at: 2026-02-23T14:30:00
    ---
    내용
"""
import re
from datetime import datetime, date, timedelta
from pathlib import Path

import frontmatter

# 데이터 디렉토리: 프로젝트 루트의 data/tils/
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "tils"


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _make_slug(title: str) -> str:
    """제목을 소문자 + 하이픈 slug로 변환한다. 한글은 제거 후 fallback."""
    slug = title.lower()
    # 영문/숫자/공백/하이픈만 유지
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug if slug else "til"


def _make_filepath(date_str: str, slug: str) -> Path:
    """파일 경로를 생성한다. 중복 시 숫자 suffix를 붙인다."""
    _ensure_dir()
    base = DATA_DIR / f"{date_str}-{slug}.md"
    if not base.exists():
        return base
    i = 2
    while True:
        candidate = DATA_DIR / f"{date_str}-{slug}-{i}.md"
        if not candidate.exists():
            return candidate
        i += 1


def _datetime_to_str(value) -> str:
    """datetime 또는 str을 ISO 문자열로 반환한다."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).isoformat()
    return str(value) if value else ""


def _load_til(filepath: Path) -> dict | None:
    """마크다운 파일에서 TIL dict를 로드한다."""
    if not filepath.exists():
        return None
    try:
        post = frontmatter.load(str(filepath))
    except Exception:
        return None

    meta = post.metadata
    created_at = _datetime_to_str(meta.get("created_at", ""))
    updated_at = _datetime_to_str(meta.get("updated_at", created_at))
    tags = meta.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)] if tags else []

    return {
        "id": meta.get("id"),
        "title": meta.get("title", ""),
        "content": post.content,
        "category": meta.get("category", "general"),
        "tags": tags,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _find_file_by_id(til_id: int) -> Path | None:
    """ID로 파일을 찾는다."""
    _ensure_dir()
    for f in DATA_DIR.glob("*.md"):
        try:
            post = frontmatter.load(str(f))
            if post.metadata.get("id") == til_id:
                return f
        except Exception:
            continue
    return None


def _save_til(filepath: Path, til_id: int, title: str, content: str,
              category: str, tags: list[str],
              created_at: str, updated_at: str) -> None:
    """TIL을 마크다운 파일에 기록한다."""
    post = frontmatter.Post(
        content=content,
        id=til_id,
        title=title,
        category=category,
        tags=tags,
        created_at=created_at,
        updated_at=updated_at,
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))


# --- TIL CRUD 함수 ---

def create_til(title: str, content: str, category: str = "general",
               tags: list[str] | None = None) -> dict:
    """새 TIL 항목을 마크다운 파일로 저장한다."""
    _ensure_dir()
    now = datetime.now()
    til_id = int(now.strftime("%Y%m%d%H%M%S"))
    date_str = now.strftime("%Y-%m-%d")
    slug = _make_slug(title)
    filepath = _make_filepath(date_str, slug)

    tag_list = [t.strip().lower() for t in (tags or []) if t.strip()]
    now_str = now.isoformat()

    _save_til(filepath, til_id, title, content, category, tag_list, now_str, now_str)
    return _load_til(filepath)


def update_til(til_id: int, title: str | None = None,
               content: str | None = None, category: str | None = None,
               tags: list[str] | None = None) -> dict:
    """기존 TIL을 수정한다. 전달된 필드만 업데이트한다."""
    filepath = _find_file_by_id(til_id)
    if not filepath:
        raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")

    existing = _load_til(filepath)
    new_title = title if title is not None else existing["title"]
    new_content = content if content is not None else existing["content"]
    new_category = category if category is not None else existing["category"]
    new_tags = (
        [t.strip().lower() for t in tags if t.strip()]
        if tags is not None
        else existing["tags"]
    )

    created_at = existing["created_at"]
    updated_at = datetime.now().isoformat()

    # 제목이 바뀌면 파일명도 변경
    if title is not None and title != existing["title"]:
        date_prefix = filepath.name[:10]  # YYYY-MM-DD
        new_slug = _make_slug(new_title)
        new_filepath = _make_filepath(date_prefix, new_slug)
        filepath.unlink()
        filepath = new_filepath

    _save_til(filepath, til_id, new_title, new_content, new_category, new_tags,
              created_at, updated_at)
    return _load_til(filepath)


def delete_til(til_id: int) -> bool:
    """TIL을 삭제한다. 삭제 성공 여부를 반환한다."""
    filepath = _find_file_by_id(til_id)
    if not filepath:
        return False
    filepath.unlink()
    return True


def search_tils(query: str, tag: str | None = None,
                category: str | None = None) -> list[dict]:
    """키워드로 TIL을 검색한다. 제목과 내용에서 검색을 수행한다."""
    _ensure_dir()
    results = []
    query_lower = query.lower()

    for f in sorted(DATA_DIR.glob("*.md"), reverse=True):
        til = _load_til(f)
        if not til:
            continue
        if (query_lower not in til["title"].lower()
                and query_lower not in til["content"].lower()):
            continue
        if tag and tag.lower() not in [t.lower() for t in til["tags"]]:
            continue
        if category and til["category"] != category:
            continue
        results.append(til)

    return results


def add_tag(til_id: int, tag: str) -> dict:
    """TIL에 단일 태그를 추가한다."""
    filepath = _find_file_by_id(til_id)
    if not filepath:
        raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")

    existing = _load_til(filepath)
    tag_clean = tag.strip().lower()
    if tag_clean and tag_clean not in existing["tags"]:
        return update_til(til_id, tags=existing["tags"] + [tag_clean])
    return existing


def get_til_by_id(til_id: int) -> dict | None:
    """ID로 TIL을 조회한다."""
    filepath = _find_file_by_id(til_id)
    if not filepath:
        return None
    return _load_til(filepath)


# --- Resource용 조회 함수 ---

def list_all_tils() -> list[dict]:
    """전체 TIL 목록을 최근순으로 반환한다."""
    _ensure_dir()
    tils = []
    for f in sorted(DATA_DIR.glob("*.md"), reverse=True):
        til = _load_til(f)
        if til:
            tils.append(til)
    return tils


def list_today_tils() -> list[dict]:
    """오늘 작성된 TIL 목록을 반환한다."""
    today = date.today().isoformat()
    return [t for t in list_all_tils() if t["created_at"][:10] == today]


def list_week_tils() -> list[dict]:
    """이번 주(최근 7일) 작성된 TIL 목록을 반환한다."""
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=6)).isoformat()
    return [t for t in list_all_tils() if week_ago <= t["created_at"][:10] <= today]


def get_stats() -> dict:
    """학습 통계를 반환한다."""
    all_tils = list_all_tils()
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=6)).isoformat()

    today_count = sum(1 for t in all_tils if t["created_at"][:10] == today)
    week_count = sum(1 for t in all_tils
                     if week_ago <= t["created_at"][:10] <= today)

    # 태그 집계
    tag_counts: dict[str, int] = {}
    for t in all_tils:
        for tag in t["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # 카테고리 집계
    cat_counts: dict[str, int] = {}
    for t in all_tils:
        cat = t["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # 최근 7일 일별 추이
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
    """특정 기간의 TIL을 조회한다. Prompt에서 사용."""
    return get_tils_for_export(date_from=date_from, date_to=date_to)


def get_tags() -> list[str]:
    """전체 태그 목록을 알파벳순으로 반환한다."""
    tag_set: set[str] = set()
    for t in list_all_tils():
        for tag in t["tags"]:
            tag_set.add(tag)
    return sorted(tag_set)


def get_categories() -> list[str]:
    """전체 카테고리 목록을 반환한다."""
    cat_set: set[str] = set()
    for t in list_all_tils():
        cat_set.add(t["category"])
    return sorted(cat_set)

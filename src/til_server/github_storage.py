"""
github_storage.py - GitHub API 기반 TIL 저장소 모듈

로컬 파일 대신 GitHub API로 마크다운 파일을 읽고 쓴다.
파일 경로: tils/YYYY-MM-DD-{slug}.md

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
import base64
import json
import os
import re
import subprocess
from datetime import datetime, date, timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import frontmatter


class GitHubStorageError(Exception):
    pass


# --- 인증 & 레포 설정 ---

def _get_token() -> str:
    """GitHub 토큰을 환경변수 또는 gh CLI에서 가져온다."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token

    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            if token:
                return token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    raise GitHubStorageError(
        "GitHub 인증이 필요합니다.\n"
        "방법 1 (추천): gh auth login\n"
        "방법 2: GITHUB_TOKEN 환경변수 설정 후 MCP 재등록"
    )


def _get_username_from_api(token: str) -> str:
    """GitHub API로 인증된 사용자명을 가져온다."""
    data = _github_api("GET", "/user", token=token)
    return data.get("login", "")


def _resolve_repo() -> str:
    """레포 이름을 환경변수 또는 gh API에서 결정한다. (owner/repo 형식)"""
    repo = os.environ.get("TIL_GITHUB_REPO", "").strip()
    if repo:
        return repo

    # gh CLI로 사용자명 시도
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            username = result.stdout.strip()
            if username:
                return f"{username}/til-notes"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # API 직접 조회
    username = _get_username_from_api(_get_token())
    if username:
        return f"{username}/til-notes"

    raise GitHubStorageError(
        "GitHub 레포지토리를 설정해주세요.\n"
        "방법: TIL_GITHUB_REPO=username/til-notes 환경변수 설정"
    )


# 모듈 레벨 캐시
_token_cache: str | None = None
_repo_cache: str | None = None


def _token() -> str:
    global _token_cache
    if _token_cache is None:
        _token_cache = _get_token()
    return _token_cache


def _repo() -> str:
    global _repo_cache
    if _repo_cache is None:
        _repo_cache = _resolve_repo()
    return _repo_cache


def _repo_name() -> str:
    return _repo().split("/", 1)[1]


# --- GitHub API 헬퍼 ---

def _github_api(method: str, path: str,
                data: dict | None = None,
                token: str | None = None) -> dict | list:
    """GitHub API 요청을 보낸다."""
    if token is None:
        token = _token()

    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data is not None else None
    req = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(err_body).get("message", err_body)
        except Exception:
            msg = err_body
        raise GitHubStorageError(f"GitHub API 오류 ({e.code}): {msg}") from e


def _is_not_found(exc: GitHubStorageError) -> bool:
    return "404" in str(exc) or "Not Found" in str(exc)


# --- 파일 유틸 ---

def _make_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug if slug else "til"


def _datetime_to_str(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).isoformat()
    return str(value) if value else ""


def _parse_til(text: str) -> dict | None:
    """마크다운 텍스트에서 TIL dict를 파싱한다."""
    try:
        post = frontmatter.loads(text)
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


def _decode_content(content_b64: str) -> str:
    """GitHub API base64 콘텐츠를 디코딩한다."""
    return base64.b64decode(content_b64.replace("\n", "")).decode("utf-8")


def _til_to_text(til_id: int, title: str, content: str, category: str,
                 tags: list[str], created_at: str, updated_at: str) -> str:
    """TIL을 마크다운 텍스트로 직렬화한다."""
    post = frontmatter.Post(
        content=content,
        id=til_id,
        title=title,
        category=category,
        tags=tags,
        created_at=created_at,
        updated_at=updated_at,
    )
    return frontmatter.dumps(post)


# --- GitHub 파일 CRUD ---

def _get_file(path: str) -> dict | None:
    """파일 내용과 sha를 가져온다. 없으면 None."""
    try:
        return _github_api("GET", f"/repos/{_repo()}/contents/{path}")
    except GitHubStorageError as e:
        if _is_not_found(e):
            return None
        raise


def _put_file(path: str, content_text: str, message: str,
              sha: str | None = None) -> None:
    """파일을 생성(sha=None) 또는 수정(sha 포함)한다."""
    content_b64 = base64.b64encode(content_text.encode("utf-8")).decode("ascii")
    data: dict = {"message": message, "content": content_b64}
    if sha:
        data["sha"] = sha
    _github_api("PUT", f"/repos/{_repo()}/contents/{path}", data=data)


def _delete_file(path: str, message: str, sha: str) -> None:
    """파일을 삭제한다."""
    _github_api("DELETE", f"/repos/{_repo()}/contents/{path}",
                data={"message": message, "sha": sha})


# --- 레포/디렉토리 초기화 ---

def _ensure_dir() -> None:
    """레포가 없으면 생성하고, tils/ 디렉토리를 초기화한다."""
    try:
        _github_api("GET", f"/repos/{_repo()}")
    except GitHubStorageError as e:
        if not _is_not_found(e):
            raise
        _github_api("POST", "/user/repos", data={
            "name": _repo_name(),
            "description": "TIL (Today I Learned) 저장소",
            "private": False,
        })

    # tils/ 디렉토리가 없으면 .gitkeep으로 초기화
    if _get_file("tils") is None:
        _put_file("tils/.gitkeep", "", "chore: tils 디렉토리 초기화")


# --- tils 목록 조회 ---

def _list_tils_meta() -> list[dict]:
    """tils/ 디렉토리의 .md 파일 메타(name, path, sha) 목록을 반환한다."""
    try:
        items = _github_api("GET", f"/repos/{_repo()}/contents/tils")
        if not isinstance(items, list):
            return []
        return [
            item for item in items
            if item.get("type") == "file"
            and item.get("name", "").endswith(".md")
        ]
    except GitHubStorageError as e:
        if _is_not_found(e):
            return []
        raise


def _load_til_from_meta(item: dict) -> dict | None:
    """파일 메타로 전체 내용을 가져와 TIL dict로 반환한다."""
    file_data = _get_file(item["path"])
    if not file_data:
        return None
    try:
        text = _decode_content(file_data.get("content", ""))
    except Exception:
        return None
    return _parse_til(text)


def _find_file_by_id(til_id: int) -> dict | None:
    """ID로 파일을 찾아 {path, sha, til} 반환. 없으면 None."""
    for item in _list_tils_meta():
        file_data = _get_file(item["path"])
        if not file_data:
            continue
        try:
            text = _decode_content(file_data.get("content", ""))
        except Exception:
            continue
        til = _parse_til(text)
        if til and til.get("id") == til_id:
            return {
                "path": item["path"],
                "sha": file_data.get("sha", ""),
                "til": til,
            }
    return None


def _make_path(date_str: str, slug: str) -> str:
    """중복 없는 GitHub 파일 경로를 생성한다."""
    existing = {item["name"] for item in _list_tils_meta()}
    base_name = f"{date_str}-{slug}.md"
    if base_name not in existing:
        return f"tils/{base_name}"
    i = 2
    while True:
        candidate = f"{date_str}-{slug}-{i}.md"
        if candidate not in existing:
            return f"tils/{candidate}"
        i += 1


# --- TIL CRUD 함수 ---

def create_til(title: str, content: str, category: str = "general",
               tags: list[str] | None = None) -> dict:
    """새 TIL 항목을 GitHub에 저장한다."""
    _ensure_dir()
    now = datetime.now()
    til_id = int(now.strftime("%Y%m%d%H%M%S"))
    date_str = now.strftime("%Y-%m-%d")
    slug = _make_slug(title)
    path = _make_path(date_str, slug)

    tag_list = [t.strip().lower() for t in (tags or []) if t.strip()]
    now_str = now.isoformat()

    text = _til_to_text(til_id, title, content, category, tag_list, now_str, now_str)
    _put_file(path, text, f"feat: TIL 추가 - {title}")

    return _parse_til(text)


def _create_til_with_metadata(til_id: int, title: str, content: str,
                               category: str, tags: list[str],
                               created_at: str, updated_at: str) -> dict:
    """마이그레이션용: 메타데이터를 보존하여 TIL을 생성한다."""
    _ensure_dir()
    date_str = created_at[:10]
    slug = _make_slug(title)
    path = _make_path(date_str, slug)

    text = _til_to_text(til_id, title, content, category, tags, created_at, updated_at)
    _put_file(path, text, f"feat: TIL 마이그레이션 - {title}")

    return _parse_til(text)


def update_til(til_id: int, title: str | None = None,
               content: str | None = None, category: str | None = None,
               tags: list[str] | None = None) -> dict:
    """기존 TIL을 수정한다. 전달된 필드만 업데이트한다."""
    found = _find_file_by_id(til_id)
    if not found:
        raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")

    existing = found["til"]
    old_path = found["path"]
    sha = found["sha"]

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

    text = _til_to_text(til_id, new_title, new_content, new_category,
                        new_tags, created_at, updated_at)

    # 제목이 바뀌면 파일명도 변경 (기존 삭제 → 새 파일 생성)
    if title is not None and title != existing["title"]:
        date_prefix = old_path.split("/")[-1][:10]  # YYYY-MM-DD
        new_slug = _make_slug(new_title)
        _delete_file(old_path,
                     f"refactor: TIL 파일명 변경 ({existing['title']} → {new_title})",
                     sha)
        new_path = _make_path(date_prefix, new_slug)
        _put_file(new_path, text, f"feat: TIL 수정 - {new_title}")
    else:
        _put_file(old_path, text, f"feat: TIL 수정 - {new_title}", sha=sha)

    return _parse_til(text)


def delete_til(til_id: int) -> bool:
    """TIL을 삭제한다. 삭제 성공 여부를 반환한다."""
    found = _find_file_by_id(til_id)
    if not found:
        return False
    _delete_file(found["path"], f"chore: TIL 삭제 #{til_id}", found["sha"])
    return True


def search_tils(query: str, tag: str | None = None,
                category: str | None = None) -> list[dict]:
    """키워드로 TIL을 검색한다. 모든 파일을 다운로드 후 필터링한다."""
    results = []
    query_lower = query.lower()

    for item in sorted(_list_tils_meta(), key=lambda x: x["name"], reverse=True):
        til = _load_til_from_meta(item)
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
    found = _find_file_by_id(til_id)
    if not found:
        raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")

    existing = found["til"]
    tag_clean = tag.strip().lower()
    if tag_clean and tag_clean not in existing["tags"]:
        return update_til(til_id, tags=existing["tags"] + [tag_clean])
    return existing


def get_til_by_id(til_id: int) -> dict | None:
    """ID로 TIL을 조회한다."""
    found = _find_file_by_id(til_id)
    return found["til"] if found else None


# --- Resource용 조회 함수 ---

def list_all_tils() -> list[dict]:
    """전체 TIL 목록을 최근순으로 반환한다."""
    tils = []
    for item in sorted(_list_tils_meta(), key=lambda x: x["name"], reverse=True):
        til = _load_til_from_meta(item)
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

    tag_counts: dict[str, int] = {}
    for t in all_tils:
        for tag in t["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
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

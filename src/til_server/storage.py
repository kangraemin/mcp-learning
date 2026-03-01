"""
storage.py - 백엔드 라우터

config.json의 backend 설정에 따라 적절한 스토리지 모듈로 위임한다.
tools.py/resources.py/prompts.py는 `from . import storage as db`로 접근하므로
이 모듈의 공개 API만 유지하면 백엔드 전환이 투명하게 동작한다.
"""
from __future__ import annotations

from typing import Any


# --- 백엔드 선택 ---

def _backend() -> Any:
    """설정 기반으로 백엔드 모듈을 동적 반환한다."""
    from .config import get_backend

    name = get_backend()
    if name == "notion":
        from . import notion_storage
        return notion_storage
    from . import github_storage
    return github_storage


# --- 초기화 ---

def _ensure_dir() -> None:
    """현재 백엔드의 초기화를 수행한다."""
    _backend()._ensure_dir()


# --- TIL CRUD ---

def create_til(title: str, content: str, category: str = "general",
               tags: list[str] | None = None) -> dict:
    return _backend().create_til(title, content, category, tags)


def update_til(til_id: int, title: str | None = None,
               content: str | None = None, category: str | None = None,
               tags: list[str] | None = None) -> dict:
    return _backend().update_til(til_id, title, content, category, tags)


def delete_til(til_id: int) -> bool:
    return _backend().delete_til(til_id)


def search_tils(query: str, tag: str | None = None,
                category: str | None = None) -> list[dict]:
    return _backend().search_tils(query, tag, category)


def add_tag(til_id: int, tag: str) -> dict:
    return _backend().add_tag(til_id, tag)


def get_til_by_id(til_id: int) -> dict | None:
    return _backend().get_til_by_id(til_id)


# --- Resource용 조회 ---

def list_all_tils() -> list[dict]:
    return _backend().list_all_tils()


def list_today_tils() -> list[dict]:
    return _backend().list_today_tils()


def list_week_tils() -> list[dict]:
    return _backend().list_week_tils()


def get_stats() -> dict:
    return _backend().get_stats()


def get_tils_for_export(til_id: int | None = None,
                        date_from: str | None = None,
                        date_to: str | None = None) -> list[dict]:
    return _backend().get_tils_for_export(til_id, date_from, date_to)


def get_tils_by_date_range(date_from: str, date_to: str) -> list[dict]:
    return _backend().get_tils_by_date_range(date_from, date_to)


def get_tags() -> list[str]:
    return _backend().get_tags()


def get_categories() -> list[str]:
    return _backend().get_categories()

"""
resources.py - MCP Resource 정의 모듈

MCP 원리 설명:
    Resource는 **읽기 전용 데이터 접근**을 위한 MCP 프리미티브이다.
    REST API의 GET 엔드포인트에 해당하며, 부작용(side effect)이 없어야 한다.
    URI 스킴(til://)으로 접근하며, LLM이 현재 상태를 파악할 때 사용한다.

    Resource Template(til://{til_id})은 동적 파라미터를 URI에 포함하여
    특정 데이터를 조회할 수 있게 한다. REST의 /items/:id 와 유사하다.

    Tool vs Resource 선택 기준:
    - 데이터를 변경하는가? → Tool 사용 (create, update, delete)
    - 데이터를 조회만 하는가? → Resource 사용 (list, stats, detail)
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from . import db


def register_resources(mcp: FastMCP) -> None:
    """모든 Resource를 FastMCP 인스턴스에 등록한다."""

    @mcp.resource("til://list")
    def list_tils() -> str:
        """전체 TIL 목록을 최근 작성순으로 조회합니다."""
        tils = db.list_all_tils()
        return json.dumps(tils, ensure_ascii=False, indent=2)

    @mcp.resource("til://list/today")
    def list_today_tils() -> str:
        """오늘 작성한 TIL 목록을 조회합니다."""
        tils = db.list_today_tils()
        return json.dumps(tils, ensure_ascii=False, indent=2)

    @mcp.resource("til://list/week")
    def list_week_tils() -> str:
        """이번 주(월~일) 작성한 TIL 목록을 조회합니다."""
        tils = db.list_week_tils()
        return json.dumps(tils, ensure_ascii=False, indent=2)

    @mcp.resource("til://{til_id}")
    def get_til_detail(til_id: str) -> str:
        """특정 TIL의 상세 내용을 조회합니다.

        Resource Template: URI의 {til_id} 부분이 함수 파라미터로 전달된다.
        예) til://42 → til_id="42"
        """
        til = db.get_til_by_id(int(til_id))
        if not til:
            raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")
        return json.dumps(til, ensure_ascii=False, indent=2)

    @mcp.resource("til://tags")
    def list_tags() -> str:
        """전체 태그 목록과 각 태그의 사용 횟수를 조회합니다."""
        tags = db.list_all_tags()
        return json.dumps(tags, ensure_ascii=False, indent=2)

    @mcp.resource("til://categories")
    def list_categories() -> str:
        """전체 카테고리 목록과 각 카테고리의 TIL 개수를 조회합니다."""
        categories = db.list_all_categories()
        return json.dumps(categories, ensure_ascii=False, indent=2)

    @mcp.resource("til://stats")
    def get_stats() -> str:
        """학습 통계를 조회합니다.

        포함 정보: 총 TIL 수, 오늘/이번 주 작성 수, 인기 태그, 카테고리 분포, 일별 추이
        """
        stats = db.get_stats()
        return json.dumps(stats, ensure_ascii=False, indent=2)

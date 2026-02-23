"""
tools.py - MCP Tool 정의 모듈

MCP 원리 설명:
    Tool은 LLM이 **행동(Action)**을 수행할 때 사용하는 MCP 프리미티브이다.
    REST API의 POST/PUT/DELETE에 해당하며, 데이터를 생성·수정·삭제하는 부작용(side effect)이 있다.

    @mcp.tool() 데코레이터를 사용하면:
    1. 함수의 타입 힌트에서 JSON Schema가 자동 생성됨
    2. docstring이 tool의 설명(description)이 됨
    3. LLM이 이 정보를 보고 언제 이 tool을 호출할지 판단함

    예: 사용자가 "오늘 배운 거 기록해줘"라고 하면
        → Claude가 create_til tool을 선택하여 호출
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import storage as db

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent


def register_tools(mcp: FastMCP) -> None:
    """모든 Tool을 FastMCP 인스턴스에 등록한다.

    server.py에서 호출되며, 이렇게 분리하면 관심사 분리(Separation of Concerns)가 가능하다.
    """

    @mcp.tool()
    def create_til(
        title: str,
        content: str,
        tags: list[str] | None = None,
        category: str = "general",
    ) -> dict:
        """새 TIL(Today I Learned) 항목을 작성합니다.

        Args:
            title: TIL 제목 (예: "Python 데코레이터 이해하기")
            content: 학습 내용 (Markdown 지원)
            tags: 태그 목록 (예: ["python", "decorator"])
            category: 카테고리 (기본값: "general")
        """
        # 입력 검증 — FastMCP가 타입은 자동 검증하지만, 비즈니스 규칙은 직접 체크
        if not title.strip():
            raise ValueError("제목은 비어있을 수 없습니다")
        if not content.strip():
            raise ValueError("내용은 비어있을 수 없습니다")

        result = db.create_til(
            title=title.strip(),
            content=content.strip(),
            category=category.strip(),
            tags=tags,
        )
        return {"status": "created", "til": result}

    @mcp.tool()
    def update_til(
        til_id: int,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """기존 TIL 항목을 수정합니다. 변경할 필드만 전달하면 됩니다.

        Args:
            til_id: 수정할 TIL의 ID
            title: 새 제목 (선택)
            content: 새 내용 (선택)
            category: 새 카테고리 (선택)
            tags: 새 태그 목록 (선택, 전달 시 기존 태그를 교체)
        """
        if title is not None and not title.strip():
            raise ValueError("제목은 비어있을 수 없습니다")

        result = db.update_til(
            til_id=til_id,
            title=title.strip() if title else None,
            content=content.strip() if content else None,
            category=category.strip() if category else None,
            tags=tags,
        )
        return {"status": "updated", "til": result}

    @mcp.tool()
    def delete_til(til_id: int) -> dict:
        """TIL 항목을 삭제합니다.

        Args:
            til_id: 삭제할 TIL의 ID
        """
        deleted = db.delete_til(til_id)
        if not deleted:
            raise LookupError(f"TIL #{til_id}을(를) 찾을 수 없습니다")
        return {"status": "deleted", "id": til_id}

    @mcp.tool()
    def search_til(
        query: str,
        tag: str | None = None,
        category: str | None = None,
    ) -> dict:
        """TIL을 키워드로 검색합니다. 제목과 내용에서 검색합니다.

        Args:
            query: 검색 키워드
            tag: 특정 태그로 필터링 (선택)
            category: 특정 카테고리로 필터링 (선택)
        """
        if not query.strip():
            raise ValueError("검색어를 입력해주세요")

        results = db.search_tils(
            query=query.strip(),
            tag=tag.strip().lower() if tag else None,
            category=category.strip() if category else None,
        )
        return {"count": len(results), "results": results}

    @mcp.tool()
    def add_tag(til_id: int, tag: str) -> dict:
        """TIL에 태그를 추가합니다.

        Args:
            til_id: 태그를 추가할 TIL의 ID
            tag: 추가할 태그 이름
        """
        if not tag.strip():
            raise ValueError("태그 이름은 비어있을 수 없습니다")

        result = db.add_tag(til_id=til_id, tag=tag.strip())
        return {"status": "tag_added", "til": result}

    @mcp.tool()
    def export_til(
        til_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        """TIL을 Markdown 형식으로 내보냅니다.

        til_id를 지정하면 해당 TIL 하나를, date_from/date_to를 지정하면 기간 내 TIL을 내보냅니다.

        Args:
            til_id: 내보낼 TIL의 ID (선택)
            date_from: 시작 날짜 (YYYY-MM-DD, 선택)
            date_to: 끝 날짜 (YYYY-MM-DD, 선택)
        """
        if til_id is None and date_from is None and date_to is None:
            raise ValueError("til_id 또는 date_from/date_to 중 하나는 지정해야 합니다")

        tils = db.get_tils_for_export(
            til_id=til_id,
            date_from=date_from,
            date_to=date_to,
        )

        if not tils:
            return {"status": "empty", "markdown": "", "count": 0}

        # Markdown 형식으로 변환
        lines = ["# TIL Export\n"]
        for til in tils:
            lines.append(f"## {til['title']}")
            lines.append(f"- **카테고리**: {til['category']}")
            lines.append(f"- **태그**: {', '.join(til['tags']) if til['tags'] else '없음'}")
            lines.append(f"- **작성일**: {til['created_at']}")
            lines.append("")
            lines.append(til["content"])
            lines.append("\n---\n")

        markdown = "\n".join(lines)
        return {"status": "exported", "markdown": markdown, "count": len(tils)}

    @mcp.tool()
    def save_discussion_recap(
        title: str,
        content: str,
        tags: list[str] | None = None,
        category: str = "discussion",
    ) -> dict:
        """현재 대화에서 논의한 내용을 요약하여 마크다운 파일로 저장합니다.

        Claude와 나눈 대화에서 특정 주제에 대해 논의한 내용을 정리할 때 사용하세요.
        저장 후 git commit + push가 자동으로 실행됩니다.

        Args:
            title: 논의 주제 제목 (예: "토큰 최적화 방안")
            content: 논의 내용 요약 (Markdown)
            tags: 태그 목록
            category: 카테고리 (기본값: "discussion")
        """
        if not title.strip():
            raise ValueError("제목은 비어있을 수 없습니다")
        if not content.strip():
            raise ValueError("내용은 비어있을 수 없습니다")

        # TIL로 저장
        til = db.create_til(
            title=title.strip(),
            content=content.strip(),
            category=category.strip(),
            tags=tags,
        )

        # 저장된 파일을 git에 추가
        # storage.py의 DATA_DIR 기반으로 파일 경로 계산
        from . import storage as _storage
        from datetime import datetime

        data_dir = _storage.DATA_DIR
        # 방금 저장된 파일 찾기 (id로)
        saved_file = _storage._find_file_by_id(til["id"])
        git_result = {"committed": False, "pushed": False, "error": None}

        if saved_file:
            try:
                rel_path = str(saved_file.relative_to(PROJECT_ROOT))
                # git add
                subprocess.run(
                    ["git", "add", rel_path],
                    cwd=str(PROJECT_ROOT),
                    check=True,
                    capture_output=True,
                )
                # git commit
                commit_msg = f"docs: {title.strip()} 논의 정리 추가"
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=str(PROJECT_ROOT),
                    check=True,
                    capture_output=True,
                )
                git_result["committed"] = True
                # git push
                push = subprocess.run(
                    ["git", "push"],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                )
                git_result["pushed"] = push.returncode == 0
                if push.returncode != 0:
                    git_result["error"] = push.stderr.strip()
            except subprocess.CalledProcessError as e:
                git_result["error"] = e.stderr.decode(errors="replace").strip() if e.stderr else str(e)

        return {"status": "saved", "til": til, "git": git_result}

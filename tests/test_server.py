"""
TIL MCP 서버 종합 테스트

테스트 DB를 별도로 사용하여 기존 데이터에 영향을 주지 않는다.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# --- 테스트 DB 설정 (fixture) ---

@pytest.fixture(autouse=True)
def test_db(tmp_path):
    """각 테스트마다 임시 DB를 사용하도록 패치한다."""
    test_db_path = tmp_path / "test_til.db"
    with mock.patch("til_server.db.DB_PATH", test_db_path):
        from til_server.db import init_db
        init_db()
        yield test_db_path


# =============================================================================
# 1. 서버 정상 실행 테스트
# =============================================================================

class TestServerStartup:
    """서버가 문법 오류 없이 정상적으로 로드되는지 테스트."""

    def test_import_server_module(self):
        """server.py가 임포트 가능한지."""
        import til_server.server
        assert til_server.server is not None

    def test_import_db_module(self):
        """db.py가 임포트 가능한지."""
        import til_server.db
        assert til_server.db is not None

    def test_import_tools_module(self):
        """tools.py가 임포트 가능한지."""
        import til_server.tools
        assert til_server.tools is not None

    def test_import_resources_module(self):
        """resources.py가 임포트 가능한지."""
        import til_server.resources
        assert til_server.resources is not None

    def test_import_prompts_module(self):
        """prompts.py가 임포트 가능한지."""
        import til_server.prompts
        assert til_server.prompts is not None

    def test_fastmcp_instance_exists(self):
        """FastMCP 인스턴스가 생성되었는지."""
        from til_server.server import mcp
        assert mcp is not None
        assert mcp.name == "TIL Server"

    def test_init_db_creates_tables(self, test_db):
        """init_db가 테이블을 생성하는지."""
        from til_server.db import get_connection
        conn = get_connection()
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row["name"] for row in tables}
            assert "tils" in table_names
            assert "tags" in table_names
            assert "til_tags" in table_names
        finally:
            conn.close()


# =============================================================================
# 2. DB CRUD 테스트 (db.py 직접 호출)
# =============================================================================

class TestDBCrud:
    """db.py의 CRUD 함수들을 직접 테스트."""

    def test_create_til_basic(self):
        """기본 TIL 생성."""
        from til_server.db import create_til
        result = create_til("테스트 제목", "테스트 내용")
        assert result["id"] == 1
        assert result["title"] == "테스트 제목"
        assert result["content"] == "테스트 내용"
        assert result["category"] == "general"
        assert result["tags"] == []

    def test_create_til_with_tags(self):
        """태그가 포함된 TIL 생성."""
        from til_server.db import create_til
        result = create_til("태그 테스트", "내용", tags=["python", "test"])
        assert "python" in result["tags"]
        assert "test" in result["tags"]

    def test_create_til_with_category(self):
        """카테고리를 지정하여 TIL 생성."""
        from til_server.db import create_til
        result = create_til("카테고리 테스트", "내용", category="backend")
        assert result["category"] == "backend"

    def test_get_til_by_id(self):
        """ID로 TIL 조회."""
        from til_server.db import create_til, get_til_by_id
        created = create_til("조회 테스트", "내용")
        fetched = get_til_by_id(created["id"])
        assert fetched is not None
        assert fetched["title"] == "조회 테스트"

    def test_get_til_by_id_not_found(self):
        """존재하지 않는 ID 조회 시 None 반환."""
        from til_server.db import get_til_by_id
        result = get_til_by_id(99999)
        assert result is None

    def test_update_til_title(self):
        """TIL 제목 수정."""
        from til_server.db import create_til, update_til
        created = create_til("원래 제목", "내용")
        updated = update_til(created["id"], title="수정된 제목")
        assert updated["title"] == "수정된 제목"
        assert updated["content"] == "내용"  # 변경 안 된 필드 유지

    def test_update_til_content(self):
        """TIL 내용 수정."""
        from til_server.db import create_til, update_til
        created = create_til("제목", "원래 내용")
        updated = update_til(created["id"], content="수정된 내용")
        assert updated["content"] == "수정된 내용"

    def test_update_til_tags(self):
        """TIL 태그 교체."""
        from til_server.db import create_til, update_til
        created = create_til("제목", "내용", tags=["old"])
        updated = update_til(created["id"], tags=["new1", "new2"])
        assert "old" not in updated["tags"]
        assert "new1" in updated["tags"]
        assert "new2" in updated["tags"]

    def test_update_til_not_found(self):
        """존재하지 않는 TIL 수정 시 LookupError."""
        from til_server.db import update_til
        with pytest.raises(LookupError):
            update_til(99999, title="없는 TIL")

    def test_delete_til(self):
        """TIL 삭제 성공."""
        from til_server.db import create_til, delete_til, get_til_by_id
        created = create_til("삭제 대상", "내용")
        assert delete_til(created["id"]) is True
        assert get_til_by_id(created["id"]) is None

    def test_delete_til_not_found(self):
        """존재하지 않는 TIL 삭제 시 False 반환."""
        from til_server.db import delete_til
        assert delete_til(99999) is False

    def test_search_tils_by_title(self):
        """제목으로 검색."""
        from til_server.db import create_til, search_tils
        create_til("Python 데코레이터", "파이썬 데코레이터 학습")
        create_til("JavaScript 클로저", "자바스크립트 클로저 학습")
        results = search_tils("Python")
        assert len(results) == 1
        assert results[0]["title"] == "Python 데코레이터"

    def test_search_tils_by_content(self):
        """내용으로 검색."""
        from til_server.db import create_til, search_tils
        create_til("제목1", "파이썬 학습 내용")
        results = search_tils("파이썬")
        assert len(results) == 1

    def test_search_tils_by_tag(self):
        """태그 필터링."""
        from til_server.db import create_til, search_tils
        create_til("제목1", "내용1", tags=["python"])
        create_til("제목2", "내용2", tags=["javascript"])
        results = search_tils("내용", tag="python")
        assert len(results) == 1
        assert results[0]["title"] == "제목1"

    def test_search_tils_by_category(self):
        """카테고리 필터링."""
        from til_server.db import create_til, search_tils
        create_til("제목1", "내용", category="backend")
        create_til("제목2", "내용", category="frontend")
        results = search_tils("내용", category="backend")
        assert len(results) == 1
        assert results[0]["title"] == "제목1"

    def test_add_tag(self):
        """TIL에 태그 추가."""
        from til_server.db import create_til, add_tag
        created = create_til("태그 추가 테스트", "내용")
        result = add_tag(created["id"], "newtag")
        assert "newtag" in result["tags"]

    def test_add_tag_not_found(self):
        """존재하지 않는 TIL에 태그 추가 시 LookupError."""
        from til_server.db import add_tag
        with pytest.raises(LookupError):
            add_tag(99999, "tag")

    def test_add_duplicate_tag(self):
        """이미 있는 태그 추가 시 중복 발생하지 않음."""
        from til_server.db import create_til, add_tag
        created = create_til("제목", "내용", tags=["python"])
        result = add_tag(created["id"], "python")
        assert result["tags"].count("python") == 1


# =============================================================================
# 3. Resource 조회 함수 테스트 (db.py)
# =============================================================================

class TestDBResources:
    """Resource에서 사용하는 db.py 조회 함수들 테스트."""

    def test_list_all_tils_empty(self):
        """TIL이 없을 때 빈 목록 반환."""
        from til_server.db import list_all_tils
        result = list_all_tils()
        assert result == []

    def test_list_all_tils(self):
        """전체 TIL 목록 조회."""
        from til_server.db import create_til, list_all_tils
        create_til("제목1", "내용1")
        create_til("제목2", "내용2")
        result = list_all_tils()
        assert len(result) == 2

    def test_list_today_tils(self):
        """오늘 TIL 조회 (생성 직후이므로 오늘 데이터)."""
        from til_server.db import create_til, list_today_tils
        create_til("오늘 TIL", "내용")
        result = list_today_tils()
        assert len(result) >= 1

    def test_list_week_tils(self):
        """이번 주 TIL 조회."""
        from til_server.db import create_til, list_week_tils
        create_til("이번 주 TIL", "내용")
        result = list_week_tils()
        assert len(result) >= 1

    def test_list_all_tags_empty(self):
        """태그가 없을 때 빈 목록."""
        from til_server.db import list_all_tags
        result = list_all_tags()
        assert result == []

    def test_list_all_tags(self):
        """태그 목록 조회."""
        from til_server.db import create_til, list_all_tags
        create_til("제목", "내용", tags=["python", "test"])
        result = list_all_tags()
        assert len(result) == 2
        tag_names = {t["name"] for t in result}
        assert "python" in tag_names
        assert "test" in tag_names

    def test_list_all_categories(self):
        """카테고리 목록 조회."""
        from til_server.db import create_til, list_all_categories
        create_til("제목1", "내용", category="backend")
        create_til("제목2", "내용", category="frontend")
        result = list_all_categories()
        assert len(result) == 2

    def test_get_stats_empty(self):
        """데이터가 없을 때 통계."""
        from til_server.db import get_stats
        stats = get_stats()
        assert stats["total"] == 0
        assert stats["today"] == 0

    def test_get_stats_with_data(self):
        """데이터가 있을 때 통계."""
        from til_server.db import create_til, get_stats
        create_til("제목1", "내용", tags=["python"])
        create_til("제목2", "내용", tags=["python", "mcp"])
        stats = get_stats()
        assert stats["total"] == 2
        assert stats["today"] >= 2
        assert len(stats["top_tags"]) >= 1

    def test_get_tils_for_export_by_id(self):
        """ID 지정 내보내기."""
        from til_server.db import create_til, get_tils_for_export
        created = create_til("내보내기 테스트", "내용")
        result = get_tils_for_export(til_id=created["id"])
        assert len(result) == 1
        assert result[0]["title"] == "내보내기 테스트"

    def test_get_tils_for_export_by_date(self):
        """날짜 범위 내보내기."""
        from til_server.db import create_til, get_tils_for_export
        create_til("제목", "내용")
        result = get_tils_for_export(date_from="2020-01-01", date_to="2030-12-31")
        assert len(result) >= 1

    def test_get_tils_for_export_not_found(self):
        """존재하지 않는 ID 내보내기."""
        from til_server.db import get_tils_for_export
        result = get_tils_for_export(til_id=99999)
        assert result == []


# =============================================================================
# 4. Tool 함수 테스트 (tools.py via FastMCP)
# =============================================================================

class TestTools:
    """tools.py에서 등록한 tool 함수들 테스트.

    FastMCP에 등록된 함수를 직접 호출하여 테스트한다.
    """

    @pytest.fixture
    def mcp_instance(self):
        """테스트용 FastMCP 인스턴스 생성."""
        from mcp.server.fastmcp import FastMCP
        from til_server.tools import register_tools
        mcp = FastMCP("Test")
        register_tools(mcp)
        return mcp

    def _get_tool_fn(self, mcp_instance, name):
        """FastMCP에서 등록된 tool의 내부 함수를 찾아 반환."""
        # FastMCP의 _tool_manager에서 tool을 찾는다
        tool = mcp_instance._tool_manager._tools.get(name)
        if tool:
            return tool.fn
        return None

    def test_create_til_tool(self, mcp_instance):
        """create_til tool 테스트."""
        fn = self._get_tool_fn(mcp_instance, "create_til")
        assert fn is not None
        result = fn(title="테스트", content="내용", tags=None, category="general")
        assert result["status"] == "created"
        assert result["til"]["title"] == "테스트"

    def test_create_til_tool_with_tags(self, mcp_instance):
        """create_til tool - 태그 포함."""
        fn = self._get_tool_fn(mcp_instance, "create_til")
        result = fn(title="태그 테스트", content="내용", tags=["python"], category="general")
        assert "python" in result["til"]["tags"]

    def test_create_til_tool_empty_title(self, mcp_instance):
        """create_til tool - 빈 제목 시 ValueError."""
        fn = self._get_tool_fn(mcp_instance, "create_til")
        with pytest.raises(ValueError):
            fn(title="  ", content="내용", tags=None, category="general")

    def test_create_til_tool_empty_content(self, mcp_instance):
        """create_til tool - 빈 내용 시 ValueError."""
        fn = self._get_tool_fn(mcp_instance, "create_til")
        with pytest.raises(ValueError):
            fn(title="제목", content="  ", tags=None, category="general")

    def test_update_til_tool(self, mcp_instance):
        """update_til tool 테스트."""
        create_fn = self._get_tool_fn(mcp_instance, "create_til")
        update_fn = self._get_tool_fn(mcp_instance, "update_til")
        created = create_fn(title="원래", content="내용", tags=None, category="general")
        til_id = created["til"]["id"]
        result = update_fn(til_id=til_id, title="수정됨", content=None, category=None, tags=None)
        assert result["status"] == "updated"
        assert result["til"]["title"] == "수정됨"

    def test_update_til_tool_empty_title(self, mcp_instance):
        """update_til tool - 빈 제목 시 ValueError."""
        create_fn = self._get_tool_fn(mcp_instance, "create_til")
        update_fn = self._get_tool_fn(mcp_instance, "update_til")
        created = create_fn(title="원래", content="내용", tags=None, category="general")
        with pytest.raises(ValueError):
            update_fn(til_id=created["til"]["id"], title="  ", content=None, category=None, tags=None)

    def test_delete_til_tool(self, mcp_instance):
        """delete_til tool 테스트."""
        create_fn = self._get_tool_fn(mcp_instance, "create_til")
        delete_fn = self._get_tool_fn(mcp_instance, "delete_til")
        created = create_fn(title="삭제 대상", content="내용", tags=None, category="general")
        result = delete_fn(til_id=created["til"]["id"])
        assert result["status"] == "deleted"

    def test_delete_til_tool_not_found(self, mcp_instance):
        """delete_til tool - 없는 ID 삭제 시 LookupError."""
        fn = self._get_tool_fn(mcp_instance, "delete_til")
        with pytest.raises(LookupError):
            fn(til_id=99999)

    def test_search_til_tool(self, mcp_instance):
        """search_til tool 테스트."""
        create_fn = self._get_tool_fn(mcp_instance, "create_til")
        search_fn = self._get_tool_fn(mcp_instance, "search_til")
        create_fn(title="Python 학습", content="데코레이터", tags=None, category="general")
        result = search_fn(query="Python", tag=None, category=None)
        assert result["count"] == 1

    def test_search_til_tool_empty_query(self, mcp_instance):
        """search_til tool - 빈 검색어 시 ValueError."""
        fn = self._get_tool_fn(mcp_instance, "search_til")
        with pytest.raises(ValueError):
            fn(query="  ", tag=None, category=None)

    def test_add_tag_tool(self, mcp_instance):
        """add_tag tool 테스트."""
        create_fn = self._get_tool_fn(mcp_instance, "create_til")
        add_tag_fn = self._get_tool_fn(mcp_instance, "add_tag")
        created = create_fn(title="제목", content="내용", tags=None, category="general")
        result = add_tag_fn(til_id=created["til"]["id"], tag="newtag")
        assert result["status"] == "tag_added"
        assert "newtag" in result["til"]["tags"]

    def test_add_tag_tool_empty(self, mcp_instance):
        """add_tag tool - 빈 태그 시 ValueError."""
        create_fn = self._get_tool_fn(mcp_instance, "create_til")
        add_tag_fn = self._get_tool_fn(mcp_instance, "add_tag")
        created = create_fn(title="제목", content="내용", tags=None, category="general")
        with pytest.raises(ValueError):
            add_tag_fn(til_id=created["til"]["id"], tag="  ")

    def test_export_til_tool_by_id(self, mcp_instance):
        """export_til tool - ID 지정."""
        create_fn = self._get_tool_fn(mcp_instance, "create_til")
        export_fn = self._get_tool_fn(mcp_instance, "export_til")
        created = create_fn(title="내보내기", content="내용입니다", tags=["test"], category="general")
        result = export_fn(til_id=created["til"]["id"], date_from=None, date_to=None)
        assert result["status"] == "exported"
        assert result["count"] == 1
        assert "# TIL Export" in result["markdown"]
        assert "내보내기" in result["markdown"]

    def test_export_til_tool_no_params(self, mcp_instance):
        """export_til tool - 파라미터 없으면 ValueError."""
        fn = self._get_tool_fn(mcp_instance, "export_til")
        with pytest.raises(ValueError):
            fn(til_id=None, date_from=None, date_to=None)

    def test_export_til_tool_empty(self, mcp_instance):
        """export_til tool - 결과 없음."""
        fn = self._get_tool_fn(mcp_instance, "export_til")
        result = fn(til_id=99999, date_from=None, date_to=None)
        assert result["status"] == "empty"
        assert result["count"] == 0


# =============================================================================
# 5. Resource 함수 테스트 (resources.py via FastMCP)
# =============================================================================

class TestResources:
    """resources.py에서 등록한 resource 함수들 테스트."""

    @pytest.fixture
    def mcp_instance(self):
        from mcp.server.fastmcp import FastMCP
        from til_server.resources import register_resources
        mcp = FastMCP("Test")
        register_resources(mcp)
        return mcp

    def _get_resource_fn(self, mcp_instance, uri):
        """FastMCP에서 등록된 resource의 내부 함수를 찾아 반환."""
        resource = mcp_instance._resource_manager._resources.get(uri)
        if resource:
            return resource.fn
        return None

    def test_list_tils_resource(self, mcp_instance):
        """til://list resource."""
        fn = self._get_resource_fn(mcp_instance, "til://list")
        assert fn is not None
        result = json.loads(fn())
        assert isinstance(result, list)

    def test_list_today_resource(self, mcp_instance):
        """til://list/today resource."""
        fn = self._get_resource_fn(mcp_instance, "til://list/today")
        assert fn is not None
        result = json.loads(fn())
        assert isinstance(result, list)

    def test_list_week_resource(self, mcp_instance):
        """til://list/week resource."""
        fn = self._get_resource_fn(mcp_instance, "til://list/week")
        assert fn is not None
        result = json.loads(fn())
        assert isinstance(result, list)

    def test_tags_resource(self, mcp_instance):
        """til://tags resource."""
        fn = self._get_resource_fn(mcp_instance, "til://tags")
        assert fn is not None
        result = json.loads(fn())
        assert isinstance(result, list)

    def test_categories_resource(self, mcp_instance):
        """til://categories resource."""
        fn = self._get_resource_fn(mcp_instance, "til://categories")
        assert fn is not None
        result = json.loads(fn())
        assert isinstance(result, list)

    def test_stats_resource(self, mcp_instance):
        """til://stats resource."""
        fn = self._get_resource_fn(mcp_instance, "til://stats")
        assert fn is not None
        result = json.loads(fn())
        assert "total" in result
        assert "today" in result
        assert "this_week" in result

    def test_list_tils_resource_with_data(self, mcp_instance):
        """데이터가 있을 때 til://list resource."""
        from til_server.db import create_til
        create_til("리소스 테스트", "내용")
        fn = self._get_resource_fn(mcp_instance, "til://list")
        result = json.loads(fn())
        assert len(result) >= 1
        assert result[0]["title"] == "리소스 테스트"

    def test_stats_resource_with_data(self, mcp_instance):
        """데이터가 있을 때 til://stats resource."""
        from til_server.db import create_til
        create_til("통계 테스트", "내용", tags=["python"])
        fn = self._get_resource_fn(mcp_instance, "til://stats")
        result = json.loads(fn())
        assert result["total"] >= 1


# =============================================================================
# 6. Resource Template 테스트 (til://{til_id})
# =============================================================================

class TestResourceTemplate:
    """Resource Template (til://{til_id}) 테스트."""

    @pytest.fixture
    def mcp_instance(self):
        from mcp.server.fastmcp import FastMCP
        from til_server.resources import register_resources
        mcp = FastMCP("Test")
        register_resources(mcp)
        return mcp

    def test_get_til_detail_template_registered(self, mcp_instance):
        """til://{til_id} 템플릿이 등록되었는지."""
        templates = mcp_instance._resource_manager._templates
        assert any("til_id" in str(t) for t in templates)

    def test_get_til_detail_function(self):
        """get_til_detail 함수 직접 호출."""
        from til_server.db import create_til, get_til_by_id
        created = create_til("상세 조회", "내용 상세")
        # resource 함수를 직접 임포트하지 않고 db 함수로 검증
        fetched = get_til_by_id(created["id"])
        assert fetched is not None
        assert fetched["title"] == "상세 조회"


# =============================================================================
# 7. Prompt 함수 테스트 (prompts.py)
# =============================================================================

class TestPrompts:
    """prompts.py에서 등록한 prompt 함수들 테스트."""

    @pytest.fixture
    def mcp_instance(self):
        from mcp.server.fastmcp import FastMCP
        from til_server.prompts import register_prompts
        mcp = FastMCP("Test")
        register_prompts(mcp)
        return mcp

    def _get_prompt_fn(self, mcp_instance, name):
        """FastMCP에서 등록된 prompt의 내부 함수를 찾아 반환."""
        prompt = mcp_instance._prompt_manager._prompts.get(name)
        if prompt:
            return prompt.fn
        return None

    def test_write_til_prompt(self, mcp_instance):
        """write_til prompt 테스트."""
        fn = self._get_prompt_fn(mcp_instance, "write_til")
        assert fn is not None
        result = fn(topic="Python 데코레이터")
        assert isinstance(result, str)
        assert "Python 데코레이터" in result
        assert "create_til" in result

    def test_weekly_review_prompt(self, mcp_instance):
        """weekly_review prompt 테스트."""
        fn = self._get_prompt_fn(mcp_instance, "weekly_review")
        assert fn is not None
        result = fn(week=None)
        assert isinstance(result, str)
        assert "이번 주" in result

    def test_weekly_review_prompt_with_week(self, mcp_instance):
        """weekly_review prompt - 주차 지정."""
        fn = self._get_prompt_fn(mcp_instance, "weekly_review")
        result = fn(week="2주차")
        assert "2주차" in result

    def test_suggest_topics_prompt(self, mcp_instance):
        """suggest_topics prompt 테스트."""
        fn = self._get_prompt_fn(mcp_instance, "suggest_topics")
        assert fn is not None
        result = fn(category=None)
        assert isinstance(result, str)
        assert "추천" in result

    def test_suggest_topics_prompt_with_category(self, mcp_instance):
        """suggest_topics prompt - 카테고리 지정."""
        fn = self._get_prompt_fn(mcp_instance, "suggest_topics")
        result = fn(category="backend")
        assert "backend" in result

    def test_summarize_learnings_prompt(self, mcp_instance):
        """summarize_learnings prompt 테스트."""
        fn = self._get_prompt_fn(mcp_instance, "summarize_learnings")
        assert fn is not None
        result = fn(date_from="2025-01-01", date_to="2025-01-31")
        assert isinstance(result, str)
        assert "2025-01-01" in result
        assert "2025-01-31" in result


# =============================================================================
# 8. 에러 케이스 및 엣지 케이스 테스트
# =============================================================================

class TestEdgeCases:
    """에러 케이스 및 엣지 케이스 테스트."""

    def test_tag_normalization(self):
        """태그가 소문자로 정규화되는지."""
        from til_server.db import create_til
        result = create_til("제목", "내용", tags=["Python", "UPPER"])
        assert "python" in result["tags"]
        assert "upper" in result["tags"]

    def test_tag_whitespace_trimming(self):
        """태그 앞뒤 공백이 제거되는지."""
        from til_server.db import create_til
        result = create_til("제목", "내용", tags=["  python  "])
        assert "python" in result["tags"]

    def test_empty_tag_ignored(self):
        """빈 태그는 무시되는지."""
        from til_server.db import create_til
        result = create_til("제목", "내용", tags=["python", "", "  "])
        assert len(result["tags"]) == 1  # "python"만

    def test_cascade_delete(self):
        """TIL 삭제 시 til_tags도 삭제되는지 (CASCADE)."""
        from til_server.db import create_til, delete_til, get_connection
        created = create_til("삭제 테스트", "내용", tags=["tag1"])
        til_id = created["id"]
        delete_til(til_id)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM til_tags WHERE til_id = ?", (til_id,)
            ).fetchall()
            assert len(rows) == 0
        finally:
            conn.close()

    def test_multiple_tils_same_tag(self):
        """여러 TIL이 같은 태그를 공유."""
        from til_server.db import create_til, list_all_tags
        create_til("제목1", "내용1", tags=["shared"])
        create_til("제목2", "내용2", tags=["shared"])
        tags = list_all_tags()
        shared = [t for t in tags if t["name"] == "shared"]
        assert len(shared) == 1
        assert shared[0]["count"] == 2

    def test_update_no_fields(self):
        """아무 필드도 변경하지 않는 update."""
        from til_server.db import create_til, update_til
        created = create_til("제목", "내용")
        result = update_til(created["id"])
        assert result["title"] == "제목"

    def test_search_no_results(self):
        """검색 결과 없음."""
        from til_server.db import search_tils
        results = search_tils("존재하지않는키워드xyz")
        assert results == []

    def test_special_characters_in_content(self):
        """특수문자가 포함된 내용."""
        from til_server.db import create_til
        content = "SELECT * FROM users WHERE id = 1; -- SQL injection test <script>alert('xss')</script>"
        result = create_til("특수문자", content)
        assert result["content"] == content

    def test_unicode_content(self):
        """유니코드(한글, 이모지 등) 내용."""
        from til_server.db import create_til
        result = create_til("한글 제목", "한글 내용 테스트")
        assert result["title"] == "한글 제목"
        assert result["content"] == "한글 내용 테스트"

    def test_export_markdown_format(self):
        """export의 마크다운 포맷 검증."""
        from til_server.db import create_til
        from mcp.server.fastmcp import FastMCP
        from til_server.tools import register_tools
        mcp = FastMCP("Test")
        register_tools(mcp)
        tool = mcp._tool_manager._tools.get("export_til")

        create_til("내보내기 제목", "내보내기 내용", tags=["tag1"], category="test")
        result = tool.fn(til_id=1, date_from=None, date_to=None)
        md = result["markdown"]
        assert "# TIL Export" in md
        assert "## 내보내기 제목" in md
        assert "**카테고리**: test" in md
        assert "tag1" in md

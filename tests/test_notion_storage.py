"""
notion_storage.py 단위 테스트

notion_client.Client를 mock하여 실제 API 호출 없이 테스트한다.
"""
from __future__ import annotations

import json
from datetime import datetime, date
from unittest import mock

import pytest


# notion_client를 mock으로 대체하여 import
@pytest.fixture(autouse=True)
def mock_notion_client():
    """notion_client 모듈을 mock으로 대체한다."""
    mock_client_cls = mock.MagicMock()
    mock_module = mock.MagicMock()
    mock_module.Client = mock_client_cls

    with mock.patch.dict("sys.modules", {"notion_client": mock_module}):
        yield mock_client_cls


@pytest.fixture(autouse=True)
def mock_config(tmp_path):
    """config를 mock하여 notion 백엔드 설정을 반환한다."""
    with mock.patch("til_server.config._config_path",
                    return_value=tmp_path / "config.json"):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "backend": "notion",
            "notion": {"token": "secret_test", "database_id": "db-test-123"},
        }))
        yield


@pytest.fixture
def notion():
    """notion_storage를 import하고 mock client를 반환한다."""
    # 캐시 초기화
    import til_server.notion_storage as ns
    ns._client_cache = None
    ns._db_id_cache = None

    # 모듈 재임포트 후 mock client 가져오기
    client_instance = ns._client()

    return {"module": ns, "client": client_instance}


# --- 헬퍼: mock 페이지 생성 ---

def _make_mock_page(til_id: int = 20260301120000,
                    title: str = "테스트 TIL",
                    category: str = "general",
                    tags: list[str] | None = None,
                    created_at: str = "2026-03-01T12:00:00",
                    updated_at: str = "2026-03-01T12:00:00",
                    page_id: str = "page-abc-123") -> dict:
    tags = tags or []
    return {
        "id": page_id,
        "object": "page",
        "properties": {
            "Name": {"title": [{"plain_text": title}]},
            "ID": {"number": til_id},
            "Category": {"select": {"name": category}},
            "Tags": {"multi_select": [{"name": t} for t in tags]},
            "Created At": {"date": {"start": created_at}},
            "Updated At": {"date": {"start": updated_at}},
        },
    }


class TestPageToTil:
    def test_converts_page_to_til(self, notion):
        ns = notion["module"]
        page = _make_mock_page(
            til_id=20260301120000,
            title="Python 학습",
            category="backend",
            tags=["python", "til"],
            created_at="2026-03-01T12:00:00",
        )
        til = ns._page_to_til(page, content="학습 내용")
        assert til["id"] == 20260301120000
        assert til["title"] == "Python 학습"
        assert til["category"] == "backend"
        assert til["tags"] == ["python", "til"]
        assert til["content"] == "학습 내용"

    def test_empty_properties(self, notion):
        ns = notion["module"]
        page = {"id": "p1", "properties": {}}
        til = ns._page_to_til(page, content="")
        assert til["id"] == 0
        assert til["title"] == ""
        assert til["category"] == "general"
        assert til["tags"] == []


class TestMarkdownBlocks:
    def test_text_to_blocks(self, notion):
        ns = notion["module"]
        blocks = ns._markdown_to_blocks("Hello\nWorld")
        assert len(blocks) == 2
        assert blocks[0]["type"] == "paragraph"
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Hello"

    def test_code_block(self, notion):
        ns = notion["module"]
        blocks = ns._markdown_to_blocks("```python\nprint('hi')\n```")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "code"
        assert blocks[0]["code"]["language"] == "python"

    def test_empty_lines_skipped(self, notion):
        ns = notion["module"]
        blocks = ns._markdown_to_blocks("Hello\n\n\nWorld")
        assert len(blocks) == 2

    def test_blocks_to_markdown(self, notion):
        ns = notion["module"]
        blocks = [
            {"type": "paragraph", "paragraph": {
                "rich_text": [{"plain_text": "Hello"}]}},
            {"type": "code", "code": {
                "rich_text": [{"plain_text": "x = 1"}],
                "language": "python"}},
        ]
        md = ns._blocks_to_markdown(blocks)
        assert "Hello" in md
        assert "```python" in md
        assert "x = 1" in md


class TestCreateTil:
    def test_creates_page(self, notion):
        ns = notion["module"]
        client = notion["client"]

        mock_page = _make_mock_page()
        client.pages.create.return_value = mock_page

        result = ns.create_til("테스트", "내용", category="general", tags=["python"])
        assert result["title"] == "테스트 TIL"  # from mock page
        client.pages.create.assert_called_once()

        call_kwargs = client.pages.create.call_args
        props = call_kwargs.kwargs.get("properties") or call_kwargs[1].get("properties")
        assert props is not None


class TestUpdateTil:
    def test_updates_properties(self, notion):
        ns = notion["module"]
        client = notion["client"]

        mock_page = _make_mock_page()
        client.databases.query.return_value = {"results": [mock_page], "has_more": False}
        client.blocks.children.list.return_value = {"results": []}
        client.pages.update.return_value = mock_page

        result = ns.update_til(20260301120000, title="수정됨")
        assert result["title"] == "수정됨"
        client.pages.update.assert_called_once()

    def test_not_found_raises(self, notion):
        ns = notion["module"]
        client = notion["client"]
        client.databases.query.return_value = {"results": [], "has_more": False}

        with pytest.raises(LookupError):
            ns.update_til(99999, title="없음")


class TestDeleteTil:
    def test_archives_page(self, notion):
        ns = notion["module"]
        client = notion["client"]

        mock_page = _make_mock_page()
        client.databases.query.return_value = {"results": [mock_page], "has_more": False}
        client.pages.update.return_value = {**mock_page, "archived": True}

        assert ns.delete_til(20260301120000) is True
        client.pages.update.assert_called_once_with(
            page_id="page-abc-123", archived=True,
        )

    def test_not_found_returns_false(self, notion):
        ns = notion["module"]
        client = notion["client"]
        client.databases.query.return_value = {"results": [], "has_more": False}

        assert ns.delete_til(99999) is False


class TestSearchTils:
    def test_filters_by_query(self, notion):
        ns = notion["module"]
        client = notion["client"]

        pages = [
            _make_mock_page(title="Python 학습", page_id="p1"),
            _make_mock_page(title="Java 학습", page_id="p2"),
        ]
        client.databases.query.return_value = {"results": pages, "has_more": False}
        client.blocks.children.list.return_value = {"results": []}

        results = ns.search_tils("Python")
        assert len(results) == 1
        assert results[0]["title"] == "Python 학습"


class TestGetTilById:
    def test_found(self, notion):
        ns = notion["module"]
        client = notion["client"]

        mock_page = _make_mock_page()
        client.databases.query.return_value = {"results": [mock_page], "has_more": False}
        client.blocks.children.list.return_value = {"results": []}

        til = ns.get_til_by_id(20260301120000)
        assert til is not None
        assert til["id"] == 20260301120000

    def test_not_found(self, notion):
        ns = notion["module"]
        client = notion["client"]
        client.databases.query.return_value = {"results": [], "has_more": False}

        assert ns.get_til_by_id(99999) is None


class TestListAllTils:
    def test_returns_all_sorted(self, notion):
        ns = notion["module"]
        client = notion["client"]

        pages = [
            _make_mock_page(til_id=1, title="첫번째", page_id="p1"),
            _make_mock_page(til_id=2, title="두번째", page_id="p2"),
        ]
        client.databases.query.return_value = {"results": pages, "has_more": False}
        client.blocks.children.list.return_value = {"results": []}

        tils = ns.list_all_tils()
        assert len(tils) == 2


class TestAddTag:
    def test_adds_new_tag(self, notion):
        ns = notion["module"]
        client = notion["client"]

        mock_page = _make_mock_page(tags=["python"])
        client.databases.query.return_value = {"results": [mock_page], "has_more": False}
        client.blocks.children.list.return_value = {"results": []}
        client.pages.update.return_value = mock_page

        result = ns.add_tag(20260301120000, "mcp")
        # update_til should have been called
        client.pages.update.assert_called()

    def test_duplicate_tag_no_update(self, notion):
        ns = notion["module"]
        client = notion["client"]

        mock_page = _make_mock_page(tags=["python"])
        client.databases.query.return_value = {"results": [mock_page], "has_more": False}
        client.blocks.children.list.return_value = {"results": []}

        result = ns.add_tag(20260301120000, "python")
        # Should NOT call pages.update since tag already exists
        client.pages.update.assert_not_called()

    def test_not_found_raises(self, notion):
        ns = notion["module"]
        client = notion["client"]
        client.databases.query.return_value = {"results": [], "has_more": False}

        with pytest.raises(LookupError):
            ns.add_tag(99999, "tag")


class TestCreateTilWithMetadata:
    def test_preserves_metadata(self, notion):
        ns = notion["module"]
        client = notion["client"]

        mock_page = _make_mock_page(
            til_id=20250101120000,
            created_at="2025-01-01T12:00:00",
            updated_at="2025-01-01T12:00:00",
        )
        client.pages.create.return_value = mock_page

        result = ns._create_til_with_metadata(
            til_id=20250101120000,
            title="마이그레이션",
            content="내용",
            category="test",
            tags=["migrated"],
            created_at="2025-01-01T12:00:00",
            updated_at="2025-01-01T12:00:00",
        )

        call_kwargs = client.pages.create.call_args
        props = call_kwargs.kwargs.get("properties") or call_kwargs[1].get("properties")
        assert props["ID"]["number"] == 20250101120000
        assert props["Created At"]["date"]["start"] == "2025-01-01T12:00:00"


class TestEnsureDir:
    def test_success(self, notion):
        ns = notion["module"]
        client = notion["client"]
        client.databases.retrieve.return_value = {"id": "db-test-123"}

        ns._ensure_dir()  # should not raise

    def test_failure_raises(self, notion):
        ns = notion["module"]
        client = notion["client"]
        client.databases.retrieve.side_effect = Exception("Not found")

        with pytest.raises(ns.NotionStorageError, match="접근할 수 없습니다"):
            ns._ensure_dir()

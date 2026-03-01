"""
storage.py 라우터 테스트

config mock으로 백엔드 전환이 올바르게 동작하는지 검증한다.
"""
from __future__ import annotations

from unittest import mock

import pytest

from til_server import storage


@pytest.fixture
def mock_github():
    """github_storage 모듈 mock."""
    m = mock.MagicMock()
    m.create_til.return_value = {"id": 1, "title": "test"}
    m.list_all_tils.return_value = [{"id": 1}]
    return m


@pytest.fixture
def mock_notion():
    """notion_storage 모듈 mock."""
    m = mock.MagicMock()
    m.create_til.return_value = {"id": 2, "title": "notion test"}
    m.list_all_tils.return_value = [{"id": 2}]
    return m


class TestBackendRouting:
    def test_default_routes_to_github(self, mock_github):
        with mock.patch("til_server.config.get_backend", return_value="github"), \
             mock.patch("til_server.storage._backend", return_value=mock_github):
            result = storage.create_til("test", "content")
            assert result["id"] == 1
            mock_github.create_til.assert_called_once()

    def test_notion_routes_to_notion(self, mock_notion):
        with mock.patch("til_server.config.get_backend", return_value="notion"), \
             mock.patch("til_server.storage._backend", return_value=mock_notion):
            result = storage.create_til("test", "content")
            assert result["id"] == 2
            mock_notion.create_til.assert_called_once()


class TestAllFunctionsDelegate:
    """모든 공개 함수가 백엔드로 위임되는지 확인."""

    @pytest.fixture
    def backend(self):
        m = mock.MagicMock()
        m.get_til_by_id.return_value = {"id": 1}
        m.delete_til.return_value = True
        m.search_tils.return_value = []
        m.add_tag.return_value = {"id": 1, "tags": ["new"]}
        m.list_all_tils.return_value = []
        m.list_today_tils.return_value = []
        m.list_week_tils.return_value = []
        m.get_stats.return_value = {"total": 0}
        m.get_tils_for_export.return_value = []
        m.get_tils_by_date_range.return_value = []
        m.get_tags.return_value = []
        m.get_categories.return_value = []
        m.create_til.return_value = {"id": 1}
        m.update_til.return_value = {"id": 1}
        return m

    def test_all_crud_functions(self, backend):
        with mock.patch("til_server.storage._backend", return_value=backend):
            storage.create_til("t", "c")
            storage.update_til(1, title="new")
            storage.delete_til(1)
            storage.search_tils("q")
            storage.add_tag(1, "tag")
            storage.get_til_by_id(1)

            assert backend.create_til.called
            assert backend.update_til.called
            assert backend.delete_til.called
            assert backend.search_tils.called
            assert backend.add_tag.called
            assert backend.get_til_by_id.called

    def test_all_resource_functions(self, backend):
        with mock.patch("til_server.storage._backend", return_value=backend):
            storage.list_all_tils()
            storage.list_today_tils()
            storage.list_week_tils()
            storage.get_stats()
            storage.get_tils_for_export()
            storage.get_tils_by_date_range("2025-01-01", "2025-01-31")
            storage.get_tags()
            storage.get_categories()

            assert backend.list_all_tils.called
            assert backend.list_today_tils.called
            assert backend.list_week_tils.called
            assert backend.get_stats.called
            assert backend.get_tils_for_export.called
            assert backend.get_tils_by_date_range.called
            assert backend.get_tags.called
            assert backend.get_categories.called

    def test_ensure_dir_delegates(self, backend):
        with mock.patch("til_server.storage._backend", return_value=backend):
            storage._ensure_dir()
            assert backend._ensure_dir.called

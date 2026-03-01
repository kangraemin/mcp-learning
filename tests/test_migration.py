"""
migrate_backend 툴 테스트

소스/타겟 백엔드를 mock하여 양방향 마이그레이션을 검증한다.
"""
from __future__ import annotations

import json
from unittest import mock

import pytest

from mcp.server.fastmcp import FastMCP
from til_server.tools import register_tools


@pytest.fixture(autouse=True)
def fake_config(tmp_path):
    """config를 임시 경로로 패치."""
    config_path = tmp_path / "config.json"
    with mock.patch("til_server.config._config_path", return_value=config_path):
        yield config_path


@pytest.fixture
def mcp_instance():
    mcp = FastMCP("Test")
    register_tools(mcp)
    return mcp


def _get_tool_fn(mcp_instance, name):
    tool = mcp_instance._tool_manager._tools.get(name)
    return tool.fn if tool else None


_SAMPLE_TILS = [
    {
        "id": 20260101120000,
        "title": "Python 데코레이터",
        "content": "데코레이터 학습 내용",
        "category": "backend",
        "tags": ["python"],
        "created_at": "2026-01-01T12:00:00",
        "updated_at": "2026-01-01T12:00:00",
    },
    {
        "id": 20260102130000,
        "title": "MCP 서버 구현",
        "content": "MCP 학습",
        "category": "general",
        "tags": ["mcp", "python"],
        "created_at": "2026-01-02T13:00:00",
        "updated_at": "2026-01-02T13:00:00",
    },
]


class TestMigrateBackendDryRun:
    def test_dry_run_github_to_notion(self, mcp_instance, fake_config):
        fake_config.write_text(json.dumps({"backend": "github"}))
        fn = _get_tool_fn(mcp_instance, "migrate_backend")

        with mock.patch("til_server.storage._backend") as mock_backend:
            mock_backend.return_value.list_all_tils.return_value = _SAMPLE_TILS
            # storage.list_all_tils 을 직접 패치
            with mock.patch("til_server.storage.list_all_tils", return_value=_SAMPLE_TILS):
                result = fn(target="notion", dry_run=True)

        assert result["status"] == "dry_run"
        assert result["source"] == "github"
        assert result["target"] == "notion"
        assert result["total"] == 2

    def test_dry_run_notion_to_github(self, mcp_instance, fake_config):
        fake_config.write_text(json.dumps({"backend": "notion"}))
        fn = _get_tool_fn(mcp_instance, "migrate_backend")

        with mock.patch("til_server.storage.list_all_tils", return_value=_SAMPLE_TILS):
            result = fn(target="github", dry_run=True)

        assert result["status"] == "dry_run"
        assert result["source"] == "notion"
        assert result["target"] == "github"


class TestMigrateBackendExecution:
    def test_github_to_notion(self, mcp_instance, fake_config):
        fake_config.write_text(json.dumps({"backend": "github"}))
        fn = _get_tool_fn(mcp_instance, "migrate_backend")

        mock_notion = mock.MagicMock()
        mock_notion._create_til_with_metadata.return_value = {"id": 1}

        with mock.patch("til_server.storage.list_all_tils", return_value=_SAMPLE_TILS), \
             mock.patch.dict("sys.modules", {"til_server.notion_storage": mock_notion}):
            result = fn(target="notion", dry_run=False)

        assert result["status"] == "completed"
        assert result["migrated"] == 2
        assert result["failed"] == []
        assert result["new_backend"] == "notion"

        # config가 변경되었는지 확인
        config = json.loads(fake_config.read_text())
        assert config["backend"] == "notion"

        # _create_til_with_metadata가 올바른 인자로 호출되었는지
        calls = mock_notion._create_til_with_metadata.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["til_id"] == 20260101120000
        assert calls[0].kwargs["created_at"] == "2026-01-01T12:00:00"

    def test_notion_to_github(self, mcp_instance, fake_config):
        fake_config.write_text(json.dumps({"backend": "notion"}))
        fn = _get_tool_fn(mcp_instance, "migrate_backend")

        mock_github = mock.MagicMock()
        mock_github._create_til_with_metadata.return_value = {"id": 1}

        with mock.patch("til_server.storage.list_all_tils", return_value=_SAMPLE_TILS), \
             mock.patch("til_server.github_storage._create_til_with_metadata",
                        mock_github._create_til_with_metadata):
            result = fn(target="github", dry_run=False)

        assert result["status"] == "completed"
        assert result["migrated"] == 2
        assert result["new_backend"] == "github"


class TestMigrateBackendErrors:
    def test_same_backend_raises(self, mcp_instance, fake_config):
        fake_config.write_text(json.dumps({"backend": "github"}))
        fn = _get_tool_fn(mcp_instance, "migrate_backend")

        with pytest.raises(ValueError, match="이미"):
            fn(target="github", dry_run=True)

    def test_invalid_target_raises(self, mcp_instance, fake_config):
        fake_config.write_text(json.dumps({"backend": "github"}))
        fn = _get_tool_fn(mcp_instance, "migrate_backend")

        with pytest.raises(ValueError, match="지원하지 않는"):
            fn(target="sqlite", dry_run=True)

    def test_partial_failure(self, mcp_instance, fake_config):
        fake_config.write_text(json.dumps({"backend": "github"}))
        fn = _get_tool_fn(mcp_instance, "migrate_backend")

        mock_notion = mock.MagicMock()
        # 첫 번째 성공, 두 번째 실패
        mock_notion._create_til_with_metadata.side_effect = [
            {"id": 1},
            Exception("API Error"),
        ]

        with mock.patch("til_server.storage.list_all_tils", return_value=_SAMPLE_TILS), \
             mock.patch.dict("sys.modules", {"til_server.notion_storage": mock_notion}):
            result = fn(target="notion", dry_run=False)

        assert result["migrated"] == 1
        assert len(result["failed"]) == 1
        assert result["failed"][0]["id"] == 20260102130000

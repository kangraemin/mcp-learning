"""
config.py 단위 테스트

tmp_path fixture로 임시 설정 파일을 사용한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from til_server.config import (
    ConfigError,
    load_config,
    save_config,
    get_backend,
    get_backend_config,
    is_first_run,
)


@pytest.fixture(autouse=True)
def fake_config_path(tmp_path):
    """모든 테스트에서 임시 경로를 사용하도록 패치."""
    config_path = tmp_path / "config.json"
    with mock.patch("til_server.config._config_path", return_value=config_path):
        yield config_path


class TestLoadConfig:
    def test_no_file_returns_default(self):
        config = load_config()
        assert config == {"backend": "github"}

    def test_reads_existing_file(self, fake_config_path):
        fake_config_path.write_text(json.dumps({
            "backend": "notion",
            "notion": {"token": "secret_abc", "database_id": "db123"},
        }))
        config = load_config()
        assert config["backend"] == "notion"
        assert config["notion"]["token"] == "secret_abc"

    def test_invalid_json_raises(self, fake_config_path):
        fake_config_path.write_text("not json {{{")
        with pytest.raises(ConfigError, match="JSON 파싱 실패"):
            load_config()

    def test_non_dict_raises(self, fake_config_path):
        fake_config_path.write_text(json.dumps([1, 2, 3]))
        with pytest.raises(ConfigError, match="형식이 잘못"):
            load_config()


class TestSaveConfig:
    def test_creates_file(self, fake_config_path):
        save_config({"backend": "github"})
        assert fake_config_path.exists()
        config = json.loads(fake_config_path.read_text())
        assert config["backend"] == "github"

    def test_creates_parent_dirs(self, tmp_path):
        nested_path = tmp_path / "a" / "b" / "config.json"
        with mock.patch("til_server.config._config_path", return_value=nested_path):
            save_config({"backend": "notion"})
        assert nested_path.exists()

    def test_overwrites_existing(self, fake_config_path):
        save_config({"backend": "github"})
        save_config({"backend": "notion"})
        config = json.loads(fake_config_path.read_text())
        assert config["backend"] == "notion"


class TestGetBackend:
    def test_default_github(self):
        assert get_backend() == "github"

    def test_notion(self, fake_config_path):
        fake_config_path.write_text(json.dumps({"backend": "notion"}))
        assert get_backend() == "notion"

    def test_invalid_backend_raises(self, fake_config_path):
        fake_config_path.write_text(json.dumps({"backend": "sqlite"}))
        with pytest.raises(ConfigError, match="잘못된 백엔드"):
            get_backend()


class TestGetBackendConfig:
    def test_empty_when_no_section(self):
        config = get_backend_config()
        assert config == {}

    def test_returns_github_section(self, fake_config_path):
        fake_config_path.write_text(json.dumps({
            "backend": "github",
            "github": {"repo": "user/til-notes"},
        }))
        config = get_backend_config()
        assert config["repo"] == "user/til-notes"

    def test_returns_notion_section(self, fake_config_path):
        fake_config_path.write_text(json.dumps({
            "backend": "notion",
            "notion": {"token": "secret_x", "database_id": "db1"},
        }))
        config = get_backend_config()
        assert config["token"] == "secret_x"
        assert config["database_id"] == "db1"


class TestIsFirstRun:
    def test_true_when_no_file(self):
        assert is_first_run() is True

    def test_false_when_file_exists(self, fake_config_path):
        fake_config_path.write_text(json.dumps({"backend": "github"}))
        assert is_first_run() is False

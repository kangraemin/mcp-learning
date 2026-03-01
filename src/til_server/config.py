"""
config.py - TIL 서버 설정 파일 관리 모듈

~/.til/config.json을 읽고 쓴다.
백엔드 선택(github/notion)과 각 백엔드별 설정을 관리한다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class ConfigError(Exception):
    pass


# --- 경로 ---

_CONFIG_DIR = Path.home() / ".til"
_CONFIG_PATH = _CONFIG_DIR / "config.json"

_DEFAULT_CONFIG: dict = {
    "backend": "github",
}

_VALID_BACKENDS = ("github", "notion")


# --- 설정 읽기/쓰기 ---

def _config_path() -> Path:
    """설정 파일 경로를 반환한다. 테스트에서 패치 가능."""
    return _CONFIG_PATH


def load_config() -> dict:
    """설정 파일을 읽어 dict로 반환한다. 없으면 기본값."""
    path = _config_path()
    if not path.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        text = path.read_text(encoding="utf-8")
        config = json.loads(text)
        if not isinstance(config, dict):
            raise ConfigError(f"설정 파일 형식이 잘못되었습니다: {path}")
        return config
    except json.JSONDecodeError as e:
        raise ConfigError(f"설정 파일 JSON 파싱 실패: {path} — {e}") from e


def save_config(config: dict) -> None:
    """설정을 파일에 저장한다. 디렉토리가 없으면 생성한다."""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# --- 설정 조회 ---

def get_backend() -> str:
    """현재 선택된 백엔드 이름을 반환한다. "github" 또는 "notion"."""
    config = load_config()
    backend = config.get("backend", "github")
    if backend not in _VALID_BACKENDS:
        raise ConfigError(
            f"잘못된 백엔드: '{backend}'. "
            f"지원 백엔드: {', '.join(_VALID_BACKENDS)}"
        )
    return backend


def get_backend_config() -> dict:
    """선택된 백엔드의 설정값을 반환한다."""
    config = load_config()
    backend = get_backend()
    return config.get(backend, {})


def is_first_run() -> bool:
    """설정 파일이 존재하지 않으면 True."""
    return not _config_path().exists()

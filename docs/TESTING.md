# Testing

## 프레임워크

- **pytest** — 단위/통합 테스트
- `tests/` 디렉토리에 테스트 파일 위치

## 빌드 검증 명령

```bash
# 패키지 설치 확인
pip show til-server

# 서버 임포트 확인
python -c "from til_server.server import mcp; print('OK')"

# 테스트 실행
pytest tests/ -v
```

## 테스트 전략

### 스토리지 백엔드
- 각 백엔드는 mock을 사용해 실제 API 호출 없이 테스트
- GitHub: `unittest.mock.patch` 로 `_github_api` 모킹
- Notion: `unittest.mock.patch` 로 `notion_client.Client` 모킹

### 마이그레이션
- 소스 백엔드에서 읽은 TIL이 타겟 백엔드에 올바르게 쓰이는지 검증
- ID, tags, created_at 보존 여부 확인

### 설정
- `~/.til/config.json` 읽기/쓰기 테스트 (tmp_path fixture 사용)

## 스킬 참조

- `.agents/skills/python-testing-patterns/` — pytest 패턴
- `.agents/skills/test-driven-development/` — TDD 워크플로우

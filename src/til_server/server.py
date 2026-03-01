"""
server.py - TIL 지식 관리 MCP 서버 메인 모듈

MCP(Model Context Protocol) 원리 설명:
    MCP는 LLM(Large Language Model)이 외부 도구와 데이터에 접근하기 위한 표준 프로토콜이다.
    서버는 세 가지 프리미티브를 클라이언트(Claude 등)에 노출한다:

    1. Tool (도구): 데이터를 변경하는 행동 — POST/PUT/DELETE에 해당
       예) TIL 생성, 수정, 삭제, 검색
    2. Resource (리소스): 읽기 전용 데이터 접근 — GET에 해당
       예) TIL 목록 조회, 통계 조회
    3. Prompt (프롬프트): 미리 정의된 지시 템플릿 — LLM의 사고를 구조화
       예) TIL 작성 가이드, 주간 회고 템플릿

    전송 방식(Transport):
    - stdio: 표준 입출력으로 통신. Claude Code와 연동할 때 가장 간편.
      클라이언트가 서버 프로세스를 직접 실행하고, stdin/stdout으로 MCP 메시지를 교환한다.

    이 서버의 구조:
    - server.py: FastMCP 인스턴스 생성 + 엔트리포인트 (이 파일)
    - storage.py: 백엔드 라우터 (config 기반으로 GitHub/Notion 선택)
    - tools.py: Tool 정의 (create, update, delete, search, add_tag, export, migrate)
    - resources.py: Resource 정의 (list, today, week, detail, tags, categories, stats)
    - prompts.py: Prompt 정의 (write_til, weekly_review, suggest_topics, summarize)
"""
from mcp.server.fastmcp import FastMCP

from .config import is_first_run, get_backend
from .tools import register_tools
from .resources import register_resources
from .prompts import register_prompts

# --- Instructions 구성 ---

_BASE_INSTRUCTIONS = (
    "학습 내용이나 대화에서 논의한 것을 기록·조회·검색할 때 이 서버의 도구를 사용하세요. "
    "기록 요청(예: '오늘 배운 거 저장해줘', '이 내용 TIL로 남겨줘')이 오면 "
    "create_til 도구로 저장하세요. "
    "목록 조회는 til://list 리소스, 검색은 search_til 도구를 사용하세요."
)

_SETUP_INSTRUCTIONS = (
    "아직 백엔드가 설정되지 않았습니다. "
    "MCP 등록 시 환경변수로 백엔드를 지정하세요. "
    "GitHub: -e TIL_BACKEND=github "
    "Notion: -e TIL_BACKEND=notion -e NOTION_TOKEN=secret_... -e NOTION_DATABASE_ID=..."
)


def _build_instructions() -> str:
    if is_first_run():
        return f"{_SETUP_INSTRUCTIONS}\n\n{_BASE_INSTRUCTIONS}"
    return _BASE_INSTRUCTIONS


# --- FastMCP 서버 인스턴스 생성 ---

mcp = FastMCP(
    "TIL Server",
    instructions=_build_instructions(),
)

# 백엔드 초기화 — 첫 실행이 아닐 때만
if not is_first_run():
    from .storage import _ensure_dir
    _ensure_dir()

# 각 모듈에서 tool/resource/prompt를 등록
register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)


# 서버 엔트리포인트
def main():
    mcp.run()


if __name__ == "__main__":
    main()

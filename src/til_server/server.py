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
    - storage.py: 파일 기반 마크다운 저장소 로직
    - tools.py: Tool 정의 (create, update, delete, search, add_tag, export, discussion_recap)
    - resources.py: Resource 정의 (list, today, week, detail, tags, categories, stats)
    - prompts.py: Prompt 정의 (write_til, weekly_review, suggest_topics, summarize)
"""
from mcp.server.fastmcp import FastMCP

from .storage import _ensure_dir
from .tools import register_tools
from .resources import register_resources
from .prompts import register_prompts

# FastMCP 서버 인스턴스 생성
# FastMCP는 Flask/FastAPI와 유사한 데코레이터 기반 API를 제공한다.
# 내부적으로 함수 시그니처의 타입 힌트를 분석하여 JSON Schema를 자동 생성한다.
mcp = FastMCP("TIL Server")

# 데이터 디렉토리 초기화 — data/tils/ 디렉토리가 없으면 생성
_ensure_dir()

# 각 모듈에서 tool/resource/prompt를 등록
# 관심사 분리(Separation of Concerns) 원칙에 따라 파일을 분리했다.
register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)


# 서버 엔트리포인트
# python -m til_server.server 또는 python server.py로 실행
def main():
    mcp.run()


if __name__ == "__main__":
    main()

#!/bin/bash
PROJECT_DIR="/Users/ram/programming/vibecoding/mcp"
SESSION="mcp-team"

# 기존 세션 정리
tmux kill-session -t "$SESSION" 2>/dev/null

# tmux 세션 생성 + 그 안에서 claude 실행
tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR" \
  "claude --teammate-mode tmux --dangerously-skip-permissions \"$(cat <<'PROMPT'
MCP 서버 학습 프로젝트야. Python FastMCP로 TIL(Today I Learned) 지식관리 MCP 서버를 만들 거야.

## 현재 상태
- docs/plan.md에 기획서가 이미 있어 (TIL 지식관리 MCP 서버로 확정)
- prompts/ 폴더에 각 역할별 프롬프트가 있어

## 팀 구성
다음 3명의 팀메이트를 만들어줘:

1. **researcher**: docs/research.md 작성. prompts/researcher.md 참고. FastMCP Python SDK 핵심 패턴, best practice, 코드 예제 조사.

2. **developer**: researcher가 docs/research.md 완성하면 시작. docs/plan.md 기획 + docs/research.md 조사 결과 바탕으로 server.py 구현. prompts/developer.md 참고. 가상환경은 source venv/bin/activate.

3. **tester**: developer가 server.py 완성하면 시작. 서버 테스트하고 docs/test-report.md 작성. prompts/tester.md 참고. 가상환경은 source venv/bin/activate.

researcher는 바로 시작하고, developer는 research.md 완성 후, tester는 server.py 완성 후 시작해줘.
작업 끝나면 git add + commit 해줘.
PROMPT
)\""

tmux attach -t "$SESSION"

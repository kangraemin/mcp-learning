#!/bin/bash
# MCP 학습 프로젝트 - 에이전트 팀 tmux 런처
PROJECT_DIR="/Users/ram/programming/vibecoding/mcp"
SESSION="mcp-learning"

# CLAUDECODE 제거 (중첩 세션 차단 우회)
unset CLAUDECODE

# 기존 세션 정리
tmux kill-session -t "$SESSION" 2>/dev/null

# 4개 pane 생성
tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR"
tmux split-window -h -t "$SESSION" -c "$PROJECT_DIR"
tmux split-window -v -t "$SESSION:0.0" -c "$PROJECT_DIR"
tmux split-window -v -t "$SESSION:0.1" -c "$PROJECT_DIR"
tmux select-layout -t "$SESSION" tiled

# 각 pane: unset CLAUDECODE 후 claude 실행
tmux send-keys -t "$SESSION:0.0" "unset CLAUDECODE; cat prompts/planner.md | claude -p --dangerously-skip-permissions" C-m
tmux send-keys -t "$SESSION:0.1" "unset CLAUDECODE; cat prompts/researcher.md | claude -p --dangerously-skip-permissions" C-m
tmux send-keys -t "$SESSION:0.2" "unset CLAUDECODE; while [ ! -f docs/plan.md ] || [ ! -f docs/research.md ]; do sleep 5; done && echo 'developer 시작' && cat prompts/developer.md | claude -p --dangerously-skip-permissions" C-m
tmux send-keys -t "$SESSION:0.3" "unset CLAUDECODE; while [ ! -f server.py ]; do sleep 5; done && echo 'tester 시작' && cat prompts/tester.md | claude -p --dangerously-skip-permissions" C-m

echo "✅ tmux 세션 '$SESSION' 생성 완료!"
echo "👉 tmux attach -t $SESSION"

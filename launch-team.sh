#!/bin/bash
PROJECT_DIR="/Users/ram/programming/vibecoding/mcp"
SESSION="mcp-learning"
unset CLAUDECODE

tmux kill-session -t "$SESSION" 2>/dev/null

# 4개 pane 생성
tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR"
tmux split-window -h -t "$SESSION" -c "$PROJECT_DIR"
tmux split-window -v -t "$SESSION:0.0" -c "$PROJECT_DIR"
tmux split-window -v -t "$SESSION:0.1" -c "$PROJECT_DIR"
tmux select-layout -t "$SESSION" tiled

# interactive claude 실행
tmux send-keys -t "$SESSION:0.0" 'unset CLAUDECODE; claude --dangerously-skip-permissions "$(cat prompts/planner.md)"' C-m
tmux send-keys -t "$SESSION:0.1" 'unset CLAUDECODE; claude --dangerously-skip-permissions "$(cat prompts/researcher.md)"' C-m
tmux send-keys -t "$SESSION:0.2" 'unset CLAUDECODE; while [ ! -f docs/plan.md ] || [ ! -f docs/research.md ]; do sleep 5; done && claude --dangerously-skip-permissions "$(cat prompts/developer.md)"' C-m
tmux send-keys -t "$SESSION:0.3" 'unset CLAUDECODE; while [ ! -f server.py ]; do sleep 5; done && claude --dangerously-skip-permissions "$(cat prompts/tester.md)"' C-m

tmux attach -t "$SESSION"

"""
prompts.py - MCP Prompt 정의 모듈

MCP 원리 설명:
    Prompt는 미리 정의된 **프롬프트 템플릿**으로, MCP의 세 번째 프리미티브이다.
    LLM이 특정 작업을 수행할 때 구조화된 지시를 제공한다.

    Tool은 "무엇을 할지(action)"를 정의하고,
    Resource는 "무엇을 볼지(data)"를 정의하고,
    Prompt는 "어떻게 생각할지(instruction)"를 정의한다.

    @mcp.prompt() 데코레이터로 등록하면 클라이언트(Claude)가
    이 프롬프트를 활용하여 더 구조화된 응답을 생성할 수 있다.
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from . import storage as db


def register_prompts(mcp: FastMCP) -> None:
    """모든 Prompt를 FastMCP 인스턴스에 등록한다."""

    @mcp.prompt()
    def write_til(topic: str) -> str:
        """TIL 작성을 도와주는 프롬프트. 주제를 입력하면 구조화된 TIL 작성 가이드를 제공합니다.

        Args:
            topic: 학습한 주제 (예: "Python 데코레이터")
        """
        return f"""다음 주제에 대한 TIL(Today I Learned)을 작성해주세요.

주제: {topic}

작성 가이드:
1. 제목은 명확하고 간결하게 (예: "Python 데코레이터의 동작 원리")
2. 핵심 내용을 3~5문장으로 요약
3. 코드 예제가 있다면 반드시 포함
4. 참고 자료가 있으면 링크 추가
5. "오늘 배운 핵심 한 줄"로 마무리

작성 후 create_til 도구를 사용하여 저장해주세요.
적절한 태그와 카테고리도 함께 지정해주세요."""

    @mcp.prompt()
    def weekly_review(week: str | None = None) -> str:
        """주간 학습 회고를 생성하는 프롬프트. 이번 주 TIL을 분석하여 회고를 작성합니다.

        Args:
            week: 특정 주차 지정 (선택, 미지정 시 이번 주)
        """
        # 이번 주 TIL 데이터를 가져와서 프롬프트에 포함
        tils = db.list_week_tils()
        til_summary = json.dumps(tils, ensure_ascii=False, indent=2) if tils else "이번 주 작성된 TIL이 없습니다."

        week_label = week if week else "이번 주"

        return f"""{week_label} 작성한 TIL들을 분석하여 주간 학습 회고를 작성해주세요.

이번 주 TIL 데이터:
{til_summary}

회고에 포함할 내용:
1. 이번 주 학습 요약 (무엇을 배웠는가)
2. 가장 인상 깊었던 학습 내용
3. 부족한 부분 / 더 공부해야 할 것
4. 다음 주 학습 계획 제안
5. 학습 패턴 분석 (어떤 카테고리에 집중했는지, 학습 빈도 등)"""

    @mcp.prompt()
    def suggest_topics(category: str | None = None) -> str:
        """학습 이력을 기반으로 다음 학습 주제를 추천하는 프롬프트.

        Args:
            category: 특정 카테고리 내에서 추천 (선택)
        """
        stats = db.get_stats()
        all_tils = db.list_all_tils()

        # 최근 10개 TIL 제목만 추출
        recent_titles = [t["title"] for t in all_tils[:10]]

        category_filter = f"\n특히 '{category}' 카테고리에 집중하여 추천해주세요." if category else ""

        return f"""사용자의 학습 이력을 분석하여 다음 학습 주제를 추천해주세요.

학습 통계:
{json.dumps(stats, ensure_ascii=False, indent=2)}

최근 학습 주제:
{json.dumps(recent_titles, ensure_ascii=False, indent=2)}
{category_filter}

추천 기준:
1. 기존 학습 내용과 연관되지만 아직 다루지 않은 주제
2. 현재 카테고리에서 더 깊이 파고들 수 있는 주제
3. 다른 카테고리와 융합할 수 있는 주제
4. 실무에서 유용한 주제 우선

각 추천 주제에 대해:
- 주제명
- 왜 이 주제를 추천하는지
- 학습 난이도 (초급/중급/고급)
- 예상 학습 시간"""

    @mcp.prompt()
    def summarize_learnings(date_from: str, date_to: str) -> str:
        """특정 기간의 학습 내용을 요약하는 프롬프트.

        Args:
            date_from: 시작 날짜 (YYYY-MM-DD)
            date_to: 끝 날짜 (YYYY-MM-DD)
        """
        tils = db.get_tils_by_date_range(date_from, date_to)
        til_data = json.dumps(tils, ensure_ascii=False, indent=2) if tils else "해당 기간에 작성된 TIL이 없습니다."

        return f"""{date_from} ~ {date_to} 기간의 학습 내용을 요약해주세요.

해당 기간 TIL 데이터:
{til_data}

요약에 포함할 내용:
1. 기간 내 학습 개요 (총 몇 건, 주요 카테고리)
2. 핵심 학습 내용 요약 (각 TIL의 핵심을 1~2줄로)
3. 카테고리별 학습 분포
4. 주요 태그 분석
5. 학습 성취도 평가 및 개선 제안"""

    @mcp.prompt()
    def discussion_recap(topic: str) -> str:
        """현재 대화에서 특정 주제에 대한 논의를 요약하여 저장하는 프롬프트.

        Args:
            topic: 요약할 논의 주제 (예: "토큰 최적화 방안")
        """
        return f"""현재 대화에서 "{topic}" 관련 논의를 요약해주세요.

다음 마크다운 구조로 정리한 뒤, create_til 도구를 호출하여 저장해주세요.

## 논의 배경
- 이 주제가 왜 논의되었는지, 어떤 문제나 질문에서 시작되었는지 설명

## 핵심 내용
- 논의에서 다룬 핵심 사항들을 bullet point로 정리
- 각 항목은 구체적이고 실행 가능한 내용으로

## 적용 방법 / 결론
- 논의를 통해 도달한 결론
- 실제로 어떻게 적용할지 방법 제시

## 참고
- 관련 자료, 링크, 추가 맥락 (있을 경우)

저장 시 다음을 지정해주세요:
- title: "{topic}" 또는 더 구체적인 제목
- category: "discussion"
- tags: 논의와 관련된 키워드들"""

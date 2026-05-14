"""
ISC-9: 单元测试验证Reflector和Planner在有LLM时使用LLM路径

测试点:
1. Reflector._reflect_llm 被调用 (不是 _reflect_simple fallback)
2. Planner.generate_plan 使用 LLM (不是 _mock_plan fallback)
3. LLM 异常时正确 fallback 到 simple/mock 路径
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.agent.reflector import Reflector, Reflection
from app.core.agent.planner import Planner, Plan, PlanStep
from app.core.agent.agent import MemoryStream, Memory, MemoryType


# ── 测试数据 ──────────────────────────────────────────

IDENTITY = "掌门"
PERSONALITY = "沉稳老练，善于决策"
SITUATION = "宗门面临外来威胁"
CURRENT_TURN = 50

LLM_REFLECTION_RESPONSE = """{
  "summary": "作为掌门，我深感宗门安危重于泰山，近期弟子们的表现让我欣慰，但也发现了一些隐患需要及时处理。",
  "patterns": ["善于观察弟子动态", "倾向于团队协作"],
  "insights": ["宗门凝聚力是应对威胁的关键", "需要加强年轻弟子的培养"],
  "recommendations": ["加强巡查山门防务", "与长老们商议对策"]
}"""

LLM_PLAN_RESPONSE = """{
  "title": "应对宗门威胁",
  "reasoning": "宗门面临威胁需要全面准备",
  "steps": [
    {"description": "召集各位长老商议对策", "target": "长老", "expected_turns": 2},
    {"description": "巡视山门防务情况", "target": "山门", "expected_turns": 2},
    {"description": "派遣弟子打探敌情", "target": "弟子", "expected_turns": 3}
  ]
}"""


# ── Mock LLM Client ───────────────────────────────────

class MockLLMClient:
    """Mock LLM client that returns structured JSON responses"""

    def __init__(self, reflection_response: str = None, plan_response: str = None):
        self.reflection_response = reflection_response or LLM_REFLECTION_RESPONSE
        self.plan_response = plan_response or LLM_PLAN_RESPONSE
        self.call_count = 0
        self.calls = []

    async def generate(self, messages: list, **kwargs) -> str:
        self.call_count += 1
        # Record call for verification
        self.calls.append({
            'messages': messages,
            'temperature': kwargs.get('temperature'),
            'max_tokens': kwargs.get('max_tokens')
        })

        # Determine which response to return based on system prompt content
        system_content = messages[0]['content'] if messages else ""
        if '反思' in system_content:
            return self.reflection_response
        elif '计划' in system_content or '规划' in system_content:
            return self.plan_response
        return self.reflection_response


class MockLLMClientFailsOnce:
    """Mock LLM that fails on first call, succeeds on second"""

    def __init__(self, response_after_fail: str = LLM_REFLECTION_RESPONSE):
        self.fail_count = 0
        self.success_response = response_after_fail
        self.call_count = 0

    async def generate(self, messages: list, **kwargs) -> str:
        self.call_count += 1
        self.fail_count += 1
        if self.fail_count == 1:
            raise Exception("LLM API unavailable")
        return self.success_response


# ── Fixtures ──────────────────────────────────────────

@pytest.fixture
def memory_stream():
    """Create a memory stream with enough memories for reflection"""
    stream = MemoryStream(agent_id="test_agent")
    # Add more than min_memories_for_reflection (10)
    for i in range(15):
        stream.add(
            content=f"[回合{i}] 测试记忆内容",
            memory_type=MemoryType.OBSERVATION if i % 2 == 0 else MemoryType.ACTION,
            turn=i,
            importance=0.6
        )
    return stream


@pytest.fixture
def reflector():
    return Reflector(
        agent_id="test_reflector",
        reflection_interval=20,
        min_memories_for_reflection=10,
        max_memories_for_prompt=15
    )


@pytest.fixture
def planner():
    return Planner(
        agent_id="test_planner",
        planning_interval=10,
        max_active_plans=2
    )


# ── Reflector Tests ───────────────────────────────────

@pytest.mark.asyncio
async def test_reflector_uses_llm_path_when_available(reflector, memory_stream):
    """ISC-9: Reflector 使用 LLM 路径 (不 fallback 到 _reflect_simple)"""
    mock_llm = MockLLMClient()
    old_reflection_count = len(reflector.reflections)

    result = await reflector.reflect(
        current_turn=CURRENT_TURN,
        memory_stream=memory_stream,
        llm_client=mock_llm,
        identity=IDENTITY,
        personality=PERSONALITY,
        situation=SITUATION
    )

    # Verify LLM was called
    assert mock_llm.call_count == 1, "LLM should be called exactly once"

    # Verify result is not from simple fallback (which uses rule-based patterns)
    assert result is not None, "Result should not be None"
    assert isinstance(result, Reflection), "Result should be a Reflection object"

    # The LLM path returns structured data - verify it's not the simple fallback
    # Simple fallback summary looks like "共15条记忆 | 其中7条动作记录"
    assert "共" not in result.summary or "记忆" not in result.summary, \
        "Should not use simple fallback (rule-based) summary"

    # Verify new reflection was created
    assert len(reflector.reflections) == old_reflection_count + 1, \
        "New reflection should be added"

    # Verify the reflection has expected structure from LLM
    assert len(result.patterns) >= 1, "Should have patterns from LLM"
    assert len(result.insights) >= 1, "Should have insights from LLM"
    assert len(result.recommendations) >= 1, "Should have recommendations from LLM"


@pytest.mark.asyncio
async def test_reflector_falls_back_on_llm_exception(reflector, memory_stream):
    """ISC-9: Reflector LLM 异常时 fallback 到 _reflect_simple"""
    mock_llm_fails = MockLLMClientFailsOnce()
    old_reflection_count = len(reflector.reflections)

    result = await reflector.reflect(
        current_turn=CURRENT_TURN,
        memory_stream=memory_stream,
        llm_client=mock_llm_fails,
        identity=IDENTITY,
        personality=PERSONALITY,
        situation=SITUATION
    )

    # Verify LLM was called (and failed)
    assert mock_llm_fails.call_count == 1, "LLM should be called on first attempt"

    # Should still get a result via fallback
    assert result is not None, "Should fallback to simple reflection when LLM fails"
    assert isinstance(result, Reflection), "Fallback result should be a Reflection"

    # Verify new reflection was created via fallback
    assert len(reflector.reflections) == old_reflection_count + 1, \
        "Fallback should still create reflection"

    # Simple fallback uses rule-based patterns, not LLM structured output
    # It should have summary containing memory stats pattern like "共15条记忆"
    summary_lower = result.summary.lower()
    assert "共" in summary_lower or "记忆" in summary_lower, \
        "Fallback summary should look like rule-based ('共X条记忆')"


@pytest.mark.asyncio
async def test_reflector_uses_simple_when_no_llm(reflector, memory_stream):
    """ISC-9: Reflector 无 LLM 时使用 _reflect_simple"""
    old_reflection_count = len(reflector.reflections)

    result = await reflector.reflect(
        current_turn=CURRENT_TURN,
        memory_stream=memory_stream,
        llm_client=None,  # No LLM
        identity=IDENTITY,
        personality=PERSONALITY,
        situation=SITUATION
    )

    # Should get result from simple path
    assert result is not None, "Should get result from simple reflection"
    assert isinstance(result, Reflection), "Result should be a Reflection"

    # Verify new reflection was created
    assert len(reflector.reflections) == old_reflection_count + 1, \
        "New reflection should be added"

    # Simple fallback summary contains memory stats
    assert "共" in result.summary, "Simple path summary should contain memory stats"


# ── Planner Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_planner_uses_llm_path_when_available(planner):
    """ISC-9: Planner 使用 LLM 路径 (不 fallback 到 _mock_plan)"""
    mock_llm = MockLLMClient()
    old_plan_count = planner._plan_counter

    result = await planner.generate_plan(
        identity=IDENTITY,
        personality=PERSONALITY,
        memories="近期弟子修为有所提升，宗门防务需要加强",
        situation=SITUATION,
        current_turn=CURRENT_TURN,
        llm_client=mock_llm
    )

    # Verify LLM was called
    assert mock_llm.call_count == 1, "LLM should be called exactly once"

    # Verify result is not from mock fallback
    assert result is not None, "Result should not be None"
    assert isinstance(result, Plan), "Result should be a Plan object"

    # Mock plan has fixed titles - LLM plan should have "应对宗门威胁"
    assert "应对宗门威胁" in result.title or "威胁" in result.title, \
        "Should use LLM plan title, not mock plan"

    # Verify plan was created with LLM response data
    assert len(result.steps) == 3, "LLM response has 3 steps"
    assert result.steps[0].description == "召集各位长老商议对策", \
        "First step should be from LLM response"

    # Verify plan is active
    assert result.status.value == "active", "Plan should be active"

    # Verify plan was added to active_plans
    assert len(planner.active_plans) >= 1, "Plan should be in active_plans"


@pytest.mark.asyncio
async def test_planner_falls_back_on_llm_exception(planner):
    """ISC-9: Planner LLM 异常时 fallback 到 _mock_plan"""
    mock_llm_fails = MockLLMClientFailsOnce(
        response_after_fail=LLM_PLAN_RESPONSE
    )
    old_plan_count = planner._plan_counter

    result = await planner.generate_plan(
        identity=IDENTITY,
        personality=PERSONALITY,
        memories="近期弟子修为有所提升，宗门防务需要加强",
        situation=SITUATION,
        current_turn=CURRENT_TURN,
        llm_client=mock_llm_fails
    )

    # Verify LLM was called (and failed first time)
    assert mock_llm_fails.call_count == 1, "LLM should be called on first attempt"

    # Should still get a result via mock fallback
    assert result is not None, "Should fallback to mock plan when LLM fails"
    assert isinstance(result, Plan), "Fallback result should be a Plan"

    # Mock plans have role-specific titles (like "巡查宗门防务")
    # Not the LLM title "应对宗门威胁"
    assert "应对宗门威胁" not in result.title, \
        "Should use mock plan title, not LLM title"

    # Verify plan was created
    assert planner._plan_counter == old_plan_count + 1, \
        "Mock fallback should still create a plan"


@pytest.mark.asyncio
async def test_planner_uses_mock_when_no_llm(planner):
    """ISC-9: Planner 无 LLM 时使用 _mock_plan"""
    old_plan_count = planner._plan_counter

    result = await planner.generate_plan(
        identity=IDENTITY,
        personality=PERSONALITY,
        memories="近期弟子修为有所提升，宗门防务需要加强",
        situation=SITUATION,
        current_turn=CURRENT_TURN,
        llm_client=None  # No LLM
    )

    # Should get result from mock path
    assert result is not None, "Should get result from mock plan"
    assert isinstance(result, Plan), "Result should be a Plan"

    # Verify plan was created
    assert planner._plan_counter == old_plan_count + 1, \
        "Mock path should create a plan"

    # Verify it's a mock plan (title from _MOCK_PLANS_BY_ROLE)
    assert result.title in ["巡查宗门防务", "培养接班人"], \
        "Should use role-specific mock plan"


@pytest.mark.asyncio
async def test_planner_invalid_llm_response_falls_back_to_mock(planner):
    """Planner receives invalid JSON from LLM, falls back to mock plan"""
    mock_llm_invalid = MockLLMClient(
        reflection_response="Not valid JSON",
        plan_response="This is not JSON at all"
    )
    # The MockLLMClient returns plan_response for plan requests
    mock_llm_invalid.plan_response = "This is not JSON at all"

    old_plan_count = planner._plan_counter

    result = await planner.generate_plan(
        identity=IDENTITY,
        personality=PERSONALITY,
        memories="近期弟子修为有所提升，宗门防务需要加强",
        situation=SITUATION,
        current_turn=CURRENT_TURN,
        llm_client=mock_llm_invalid
    )

    # LLM was called (even though response was invalid)
    assert mock_llm_invalid.call_count == 1, "LLM should be called"

    # But we should get a fallback plan since JSON parsing failed
    assert result is not None, "Should fallback to mock plan on invalid JSON"
    assert isinstance(result, Plan), "Result should be a Plan"

    # Should still create a plan
    assert planner._plan_counter == old_plan_count + 1, \
        "Fallback should still create a plan"


# ── Run Tests ─────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
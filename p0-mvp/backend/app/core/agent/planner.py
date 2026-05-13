"""
C01 规划模块 — LLM驱动的中短期计划生成
每N回合基于记忆+身份+环境生成结构化计划
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from ..sandbox.action_executor import BaseLLMClient


class PlanStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass
class PlanStep:
    step_id: str
    description: str
    target: Optional[str] = None
    expected_turns: int = 1
    conditions: List[str] = field(default_factory=list)

    def is_achievable(self, current_state: Dict) -> bool:
        for condition in self.conditions:
            if "NOT" in condition and condition.split("NOT")[1].strip() in current_state:
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.step_id,
            "description": self.description,
            "target": self.target,
            "expected_turns": self.expected_turns,
        }


@dataclass
class Plan:
    plan_id: str
    title: str
    steps: List[PlanStep]
    current_step: int = 0
    status: PlanStatus = PlanStatus.ACTIVE
    created_turn: int = 0
    completed_turn: Optional[int] = None
    failure_reason: Optional[str] = None

    @property
    def current_step_obj(self) -> Optional[PlanStep]:
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    @property
    def progress_pct(self) -> float:
        if not self.steps:
            return 0
        return self.current_step / len(self.steps)

    def advance(self) -> bool:
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.status = PlanStatus.COMPLETED
            return True
        return False

    def fail(self, reason: str):
        self.status = PlanStatus.FAILED
        self.failure_reason = reason

    def abandon(self):
        self.status = PlanStatus.ABANDONED

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step,
            "progress_pct": round(self.progress_pct, 2),
            "status": self.status.value,
            "created_turn": self.created_turn,
        }


# ── 计划生成提示词模板 ──────────────────────────────

PLAN_SYSTEM_PROMPT = """你是一个角色行为规划专家。你需要为虚构角色生成清晰的行动计划。

格式要求：返回JSON，不要其他内容：
{
  "title": "计划标题(10字以内)",
  "reasoning": "为什么制定此计划(20字以内)",
  "steps": [
    {"description": "第一步具体行动", "target": "目标角色名或地点(可选)", "expected_turns": 2},
    {"description": "第二步具体行动", "target": "目标角色名或地点(可选)", "expected_turns": 3},
    {"description": "第三步具体行动", "target": "目标角色名或地点(可选)", "expected_turns": 2}
  ]
}

规则：
- 计划必须有3步，每步expected_turns为1-5之间的整数
- 步骤必须具体可执行（不能是"探索环境"这种空泛描述）
- target是可选的，如果步骤有明确目标角色或地点就填
- 计划要符合角色的身份、性格和当前处境"""


# ── 角色化Mock计划库 ──────────────────────────────────

_MOCK_PLANS_BY_ROLE = {
    "掌门": [
        {"title": "巡查宗门防务", "steps": [
            {"description": "巡视山门守卫情况", "target": "山门", "expected_turns": 1},
            {"description": "召集长老议事", "target": "长老", "expected_turns": 2},
            {"description": "颁布新的宗门法令", "target": None, "expected_turns": 1},
        ]},
        {"title": "培养接班人", "steps": [
            {"description": "考核弟子功法进展", "target": "弟子", "expected_turns": 2},
            {"description": "传授独门心法", "target": "弟子", "expected_turns": 3},
            {"description": "安排下山历练任务", "target": None, "expected_turns": 2},
        ]},
    ],
    "弟子": [
        {"title": "突破修炼瓶颈", "steps": [
            {"description": "向师父请教功法疑难", "target": "师父", "expected_turns": 1},
            {"description": "闭关修炼冲击瓶颈", "target": None, "expected_turns": 3},
            {"description": "找同门切磋验证实力", "target": "同门", "expected_turns": 2},
        ]},
        {"title": "寻觅炼丹材料", "steps": [
            {"description": "查阅古籍寻找药材线索", "target": None, "expected_turns": 1},
            {"description": "前往妖兽林采集药材", "target": "妖兽林", "expected_turns": 3},
            {"description": "回炼丹房尝试炼丹", "target": "炼丹房", "expected_turns": 2},
        ]},
    ],
    "长老": [
        {"title": "炼制珍稀丹药", "steps": [
            {"description": "检查丹炉状态准备材料", "target": None, "expected_turns": 1},
            {"description": "点火炼丹控制火候", "target": None, "expected_turns": 3},
            {"description": "开炉检验丹药品质", "target": None, "expected_turns": 1},
        ]},
    ],
    "游侠": [
        {"title": "追查神秘事件真相", "steps": [
            {"description": "走访客栈收集线索", "target": "悦来客栈", "expected_turns": 2},
            {"description": "追踪可疑人物行踪", "target": None, "expected_turns": 3},
            {"description": "揭发幕后黑手", "target": None, "expected_turns": 2},
        ]},
    ],
    "方丈": [
        {"title": "维护武林安宁", "steps": [
            {"description": "召集各派商议武林大会事宜", "target": "各派掌门", "expected_turns": 2},
            {"description": "调解江湖纷争", "target": None, "expected_turns": 3},
            {"description": "派遣弟子维持会场秩序", "target": "弟子", "expected_turns": 1},
        ]},
    ],
    "所长": [
        {"title": "调查灵异委托", "steps": [
            {"description": "接取新委托了解案情", "target": "委托人", "expected_turns": 1},
            {"description": "深入灵异现场勘查线索", "target": None, "expected_turns": 3},
            {"description": "制定驱魔方案执行超度", "target": None, "expected_turns": 2},
        ]},
    ],
    "_default": [
        {"title": "了解当前处境", "steps": [
            {"description": "观察周围环境和人员动向", "target": None, "expected_turns": 1},
            {"description": "与关键人物交谈获取信息", "target": None, "expected_turns": 2},
            {"description": "基于情报决定下一步行动", "target": None, "expected_turns": 1},
        ]},
    ],
}


def _match_mock_plan(identity: str) -> dict:
    """根据角色身份匹配Mock计划"""
    for keyword, plans in _MOCK_PLANS_BY_ROLE.items():
        if keyword in identity:
            import random
            return random.choice(plans)
    import random
    return random.choice(_MOCK_PLANS_BY_ROLE["_default"])


class Planner:
    """LLM驱动的规划模块"""

    def __init__(
        self,
        agent_id: str,
        planning_interval: int = 10,
        max_active_plans: int = 2,
    ):
        self.agent_id = agent_id
        self.planning_interval = planning_interval
        self.max_active_plans = max_active_plans

        self.active_plans: List[Plan] = []
        self.completed_plans: List[Plan] = []
        self.failed_plans: List[Plan] = []

        self._plan_counter = 0
        self._step_counter = 0
        self._last_plan_turn = 0

    def should_replan(self, current_turn: int) -> bool:
        if not self.active_plans:
            return True
        for plan in self.active_plans:
            if current_turn - plan.created_turn >= self.planning_interval:
                return True
        return False

    # ── LLM 计划生成 ───────────────────────────────

    async def generate_plan(
        self,
        identity: str,
        personality: str,
        memories: str,
        situation: str,
        current_turn: int,
        llm_client: "BaseLLMClient",
    ) -> Optional[Plan]:
        """使用LLM生成结构化计划"""
        self._plan_counter += 1
        plan_id = f"{self.agent_id}_plan_{self._plan_counter}"

        user_prompt = f"""角色身份：{identity}
性格特点：{personality}
当前处境：{situation}

近期记忆：
{memories}

请为这个角色生成接下来{self.planning_interval}回合的行动计划。"""

        messages = [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await llm_client.generate(messages, temperature=0.7, max_tokens=500)
            plan_data = self._parse_plan_response(response, plan_id)
        except Exception:
            plan_data = None

        if plan_data is None:
            return self._mock_plan(identity, plan_id, current_turn)

        steps = [
            PlanStep(
                step_id=f"{plan_id}_step_{i+1}",
                description=s.get("description", "继续当前行动"),
                target=s.get("target"),
                expected_turns=min(5, max(1, s.get("expected_turns", 2))),
            )
            for i, s in enumerate(plan_data.get("steps", []))
        ]

        if len(steps) < 2:
            return self._mock_plan(identity, plan_id, current_turn)

        plan = Plan(
            plan_id=plan_id,
            title=plan_data.get("title", "行动计划"),
            steps=steps,
            created_turn=current_turn,
        )

        self._activate_plan(plan)
        self._last_plan_turn = current_turn
        return plan

    def _parse_plan_response(self, response: Optional[str], plan_id: str) -> Optional[dict]:
        """解析LLM返回的JSON计划"""
        if not response:
            return None
        try:
            # 尝试提取JSON块
            json_match = re.search(r'\{[\s\S]*"title"[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(response)
        except (json.JSONDecodeError, KeyError):
            return None

    def _mock_plan(self, identity: str, plan_id: str, current_turn: int) -> Plan:
        """角色化Mock计划（无LLM时的智能fallback）"""
        template = _match_mock_plan(identity)
        steps = [
            PlanStep(
                step_id=f"{plan_id}_step_{i+1}",
                description=s["description"],
                target=s.get("target"),
                expected_turns=s.get("expected_turns", 2),
            )
            for i, s in enumerate(template["steps"])
        ]
        plan = Plan(
            plan_id=plan_id,
            title=template["title"],
            steps=steps,
            created_turn=current_turn,
        )
        self._activate_plan(plan)
        self._last_plan_turn = current_turn
        return plan

    def create_simple_plan(self, goal: str, current_turn: int, steps: List[str]) -> Plan:
        """以简单目标创建计划"""
        self._plan_counter += 1
        plan_id = f"{self.agent_id}_plan_{self._plan_counter}"
        plan_steps = [
            PlanStep(step_id=f"{plan_id}_step_{i+1}", description=desc, expected_turns=2)
            for i, desc in enumerate(steps)
        ]
        plan = Plan(plan_id=plan_id, title=goal, steps=plan_steps, created_turn=current_turn)
        self._activate_plan(plan)
        self._last_plan_turn = current_turn
        return plan

    def _activate_plan(self, plan: Plan):
        while len(self.active_plans) >= self.max_active_plans:
            old = self.active_plans.pop(0)
            old.abandon()
            self.failed_plans.append(old)
        self.active_plans.append(plan)

    # ── 计划执行追踪 ───────────────────────────────

    def get_current_goal(self) -> Optional[str]:
        if self.active_plans:
            step = self.active_plans[0].current_step_obj
            return step.description if step else None
        return None

    def get_action_context(self) -> str:
        """生成行动上下文（注入到action prompt中）"""
        if not self.active_plans:
            return "你目前没有明确的计划，可以自由探索。"
        plan = self.active_plans[0]
        step = plan.current_step_obj
        parts = [f"当前计划：{plan.title}"]
        if step:
            parts.append(f"当前步骤：{step.description}")
            if step.target:
                parts.append(f"目标对象：{step.target}")
        next_steps = [
            s.description for s in plan.steps[plan.current_step + 1:plan.current_step + 3]
        ]
        if next_steps:
            parts.append(f"后续步骤：{' → '.join(next_steps)}")
        return "\n".join(parts)

    def progress(self, current_turn: int, action_result: Optional[str] = None) -> bool:
        """推进计划（基于回合流逝和行动结果）"""
        if not self.active_plans:
            return False
        plan = self.active_plans[0]
        step = plan.current_step_obj
        if not step:
            return False
        # 每expected_turns推进一步
        turns_on_step = current_turn - plan.created_turn - plan.current_step * step.expected_turns
        if turns_on_step >= step.expected_turns:
            if plan.advance():
                self.completed_plans.append(plan)
                self.active_plans.pop(0)
                return True
        return False

    def fail_current(self, reason: str):
        if self.active_plans:
            plan = self.active_plans.pop(0)
            plan.fail(reason)
            self.failed_plans.append(plan)

    def abandon_all(self):
        while self.active_plans:
            plan = self.active_plans.pop(0)
            plan.abandon()
            self.failed_plans.append(plan)

    def get_status(self) -> Dict:
        return {
            "active_plans": len(self.active_plans),
            "completed_plans": len(self.completed_plans),
            "failed_plans": len(self.failed_plans),
            "current_goal": self.get_current_goal(),
            "current_plan": self.active_plans[0].to_dict() if self.active_plans else None,
        }

    def to_dict(self) -> dict:
        return {
            **self.get_status(),
            "completed_titles": [p.title for p in self.completed_plans[-3:]],
        }

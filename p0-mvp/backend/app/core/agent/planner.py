"""
C01 规划模块
每N回合生成一次中短期计划
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from datetime import datetime
from enum import Enum


class PlanStatus(Enum):
    """计划状态"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass
class PlanStep:
    """计划步骤"""
    step_id: str
    description: str
    target: Optional[str] = None
    expected_turns: int = 1
    conditions: List[str] = field(default_factory=list)
    
    def is_achievable(self, current_state: Dict) -> bool:
        """检查条件是否满足"""
        for condition in self.conditions:
            # 简化实现：实际应解析条件表达式
            if "NOT" in condition and condition.split("NOT")[1].strip() in current_state:
                return False
        return True


@dataclass
class Plan:
    """计划"""
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
    
    def advance(self) -> bool:
        """推进到下一步"""
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.status = PlanStatus.COMPLETED
            return True
        return False
    
    def fail(self, reason: str):
        """标记为失败"""
        self.status = PlanStatus.FAILED
        self.failure_reason = reason
    
    def abandon(self):
        """放弃计划"""
        self.status = PlanStatus.ABANDONED
    
    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "steps": [
                {"id": s.step_id, "description": s.description, "target": s.target}
                for s in self.steps
            ],
            "current_step": self.current_step,
            "status": self.status.value,
            "created_turn": self.created_turn
        }


class Planner:
    """
    规划模块
    
    负责：
    - 生成中短期计划
    - 跟踪计划执行
    - 动态调整计划
    """
    
    def __init__(
        self,
        agent_id: str,
        planning_interval: int = 10,  # 每N回合重新规划
        max_active_plans: int = 2
    ):
        self.agent_id = agent_id
        self.planning_interval = planning_interval
        self.max_active_plans = max_active_plans
        
        self.active_plans: List[Plan] = []
        self.completed_plans: List[Plan] = []
        self.failed_plans: List[Plan] = []
        
        self._plan_counter = 0
        self._step_counter = 0
    
    def should_replan(self, current_turn: int) -> bool:
        """检查是否需要重新规划"""
        # 没有活跃计划
        if not self.active_plans:
            return True
        
        # 到了规划周期
        for plan in self.active_plans:
            turns_since_creation = current_turn - plan.created_turn
            if turns_since_creation >= self.planning_interval:
                return True
        
        return False
    
    async def generate_plan(
        self,
        goal: str,
        current_turn: int,
        llm_client: Callable
    ) -> Optional[Plan]:
        """
        生成计划（使用LLM）
        
        简化实现：生成基本计划结构
        """
        self._plan_counter += 1
        plan_id = f"{self.agent_id}_plan_{self._plan_counter}"
        
        # 简化：直接生成简单计划
        # 实际应调用LLM生成
        steps = [
            PlanStep(
                step_id=f"{plan_id}_step_1",
                description=f"探索环境，了解情况",
                expected_turns=2
            ),
            PlanStep(
                step_id=f"{plan_id}_step_2",
                description=f"寻找机会推进目标：{goal}",
                expected_turns=5
            ),
            PlanStep(
                step_id=f"{plan_id}_step_3",
                description=f"评估进展，调整策略",
                expected_turns=3
            )
        ]
        
        plan = Plan(
            plan_id=plan_id,
            title=goal,
            steps=steps,
            created_turn=current_turn
        )
        
        # 移除多余计划
        while len(self.active_plans) >= self.max_active_plans:
            old = self.active_plans.pop(0)
            old.abandon()
            self.failed_plans.append(old)
        
        self.active_plans.append(plan)
        
        return plan
    
    def create_simple_plan(
        self,
        goal: str,
        current_turn: int,
        steps: List[str]
    ) -> Plan:
        """创建简单计划"""
        self._plan_counter += 1
        plan_id = f"{self.agent_id}_plan_{self._plan_counter}"
        
        plan_steps = []
        for i, desc in enumerate(steps):
            self._step_counter += 1
            plan_steps.append(PlanStep(
                step_id=f"{plan_id}_step_{i+1}",
                description=desc,
                expected_turns=2
            ))
        
        plan = Plan(
            plan_id=plan_id,
            title=goal,
            steps=plan_steps,
            created_turn=current_turn
        )
        
        while len(self.active_plans) >= self.max_active_plans:
            old = self.active_plans.pop(0)
            old.abandon()
            self.failed_plans.append(old)
        
        self.active_plans.append(plan)
        return plan
    
    def get_current_goal(self) -> Optional[str]:
        """获取当前目标"""
        if self.active_plans:
            current = self.active_plans[0].current_step_obj
            if current:
                return current.description
        return None
    
    def progress(self, current_turn: int) -> bool:
        """
        推进计划
        
        Returns:
            True if progress made, False otherwise
        """
        if not self.active_plans:
            return False
        
        plan = self.active_plans[0]
        step = plan.current_step_obj
        
        if not step:
            return False
        
        # 检查是否需要推进到下一步
        # 简化：每次调用都尝试推进
        if plan.advance():
            self.completed_plans.append(plan)
            self.active_plans.pop(0)
            return True
        
        return True
    
    def fail_current(self, reason: str):
        """标记当前计划失败"""
        if self.active_plans:
            plan = self.active_plans.pop(0)
            plan.fail(reason)
            self.failed_plans.append(plan)
    
    def abandon_all(self):
        """放弃所有计划"""
        while self.active_plans:
            plan = self.active_plans.pop(0)
            plan.abandon()
            self.failed_plans.append(plan)
    
    def get_status(self) -> Dict:
        """获取规划状态"""
        return {
            "active_plans": len(self.active_plans),
            "completed_plans": len(self.completed_plans),
            "failed_plans": len(self.failed_plans),
            "current_goal": self.get_current_goal(),
            "current_plan": self.active_plans[0].to_dict() if self.active_plans else None
        }

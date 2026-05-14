"""
S2-6 World Info 预算管理器
按回合总预算池分配 Lorebook 注入配额，优先保障关键角色
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentBudget:
    """单个Agent的预算分配"""
    agent_id: str
    agent_name: str
    allocation: int          # 本轮分配字符数
    used: int = 0            # 实际使用字符数
    lore_entries: int = 0    # 注入词条数
    priority: float = 0.0    # 分配优先级 (0-1)


class BudgetManager:
    """
    World Info 预算管理器

    每回合总预算池按 NPC 重要性分配，优先保障：
    1. 近期有互动的角色（故事密度高）
    2. 有关键目标的角色（主角团）
    3. 剩余名额均分给其他角色

    未用完预算滚入下回合（衰减 50%）
    """

    def __init__(self, total_chars_per_turn: int = 2000, rollover_decay: float = 0.5):
        self.total_budget = total_chars_per_turn
        self.rollover_decay = rollover_decay
        self.rollover = 0                          # 滚存预算
        self.current_allocations: dict[str, AgentBudget] = {}
        self._turn = 0
        self._total_used = 0

    def allocate(
        self,
        agents: dict,
        recent_targets: set[str],
        turn: int,
    ) -> dict[str, int]:
        """
        为本回合分配预算

        Args:
            agents: {agent_id: Agent} 字典
            recent_targets: 近N回合有互动的 agent_id 集合
            turn: 当前回合号

        Returns:
            {agent_id: budget_chars} 分配表
        """
        self._turn = turn
        self.current_allocations.clear()

        available = self.total_budget + int(self.rollover * self.rollover_decay)
        n = len(agents)
        if n == 0:
            self.rollover = available
            return {}

        # 优先级评分 (0-1)
        scores: dict[str, float] = {}
        for aid, agent in agents.items():
            score = 0.3  # 基础分
            if aid in recent_targets:
                score += 0.3       # 近期互动
            if agent.planner and agent.planner.current_plan:
                score += 0.2       # 有活跃计划
            if agent.planner and agent.planner.completed_plans > 0:
                score += 0.1
            scores[aid] = min(score, 1.0)

        total_score = sum(scores.values()) or 1.0

        # 按优先级加权分配 (保留 10% 基础保底)
        base_share = int(available * 0.1 / n)  # 每人保底
        weighted_pool = available - base_share * n

        allocations: dict[str, int] = {}
        for aid in agents:
            weighted = int(weighted_pool * scores[aid] / total_score)
            budget = base_share + weighted
            # 单 agent 上限 40%
            budget = min(budget, int(available * 0.4))
            allocations[aid] = budget
            self.current_allocations[aid] = AgentBudget(
                agent_id=aid,
                agent_name=agents[aid].config.name,
                allocation=budget,
                priority=scores[aid],
            )

        return allocations

    def track_usage(self, agent_id: str, chars_used: int, lore_entries: int = 0):
        """记录实际使用量"""
        if agent_id in self.current_allocations:
            b = self.current_allocations[agent_id]
            b.used += chars_used
            b.lore_entries += lore_entries

    def finish_turn(self):
        """回合结束，计算滚存"""
        used = sum(b.used for b in self.current_allocations.values())
        self._total_used = used
        surplus = self.total_budget - used
        self.rollover = max(0, surplus)

    def get_stats(self) -> dict:
        """预算使用统计"""
        allocs = self.current_allocations
        total_alloc = sum(b.allocation for b in allocs.values())
        total_used = sum(b.used for b in allocs.values())

        return {
            "turn": self._turn,
            "total_budget": self.total_budget,
            "rollover": self.rollover,
            "total_allocated": total_alloc,
            "total_used": total_used,
            "usage_pct": round(total_used / self.total_budget * 100, 1) if self.total_budget else 0,
            "agent_count": len(allocs),
            "agents": [
                {
                    "agent_id": b.agent_id,
                    "name": b.agent_name,
                    "allocation": b.allocation,
                    "used": b.used,
                    "usage_pct": round(b.used / b.allocation * 100, 1) if b.allocation else 0,
                    "lore_entries": b.lore_entries,
                    "priority": round(b.priority, 2),
                }
                for b in sorted(allocs.values(), key=lambda b: b.priority, reverse=True)
            ],
        }

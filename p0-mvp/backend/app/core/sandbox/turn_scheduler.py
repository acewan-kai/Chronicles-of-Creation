"""
A01 回合调度器
负责回合的顺序执行、进度跟踪、超时控制
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TurnStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TurnMetrics:
    """回合指标"""
    turn_number: int
    start_time: float
    end_time: Optional[float] = None
    npc_count: int = 0
    success_count: int = 0
    fallback_count: int = 0
    max_npc_delay: float = 0.0
    status: TurnStatus = TurnStatus.PENDING
    
    @property
    def elapsed_time(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time


class TurnScheduler:
    """
    回合调度器
    管理回合的执行顺序、并发控制、进度跟踪
    """
    
    def __init__(
        self,
        total_turns: int = 100,
        turns_per_day: int = 8,
        max_concurrency: int = 10,
        turn_timeout: float = 30.0
    ):
        self.total_turns = total_turns
        self.turns_per_day = turns_per_day
        self.max_concurrency = max_concurrency
        self.turn_timeout = turn_timeout
        
        self.current_turn = 0
        self.history: List[TurnMetrics] = []
        self._running = False
        self._paused = False
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def is_paused(self) -> bool:
        return self._paused
    
    def pause(self):
        """暂停调度"""
        self._paused = True
    
    def resume(self):
        """恢复调度"""
        self._paused = False
    
    def stop(self):
        """停止调度"""
        self._running = False
        self._paused = False
    
    async def run_turn(
        self,
        turn_number: int,
        npc_tasks: List[Callable],
        progress_callback: Optional[Callable] = None
    ) -> TurnMetrics:
        """
        执行单个回合
        
        Args:
            turn_number: 回合编号
            npc_tasks: NPC动作任务列表（每个任务是协程）
            progress_callback: 进度回调函数
            
        Returns:
            TurnMetrics: 回合执行指标
        """
        metrics = TurnMetrics(
            turn_number=turn_number,
            start_time=time.time(),
            npc_count=len(npc_tasks)
        )
        
        print(f"\n{'='*60}")
        print(f"回合 {turn_number} | 第{(turn_number-1)//self.turns_per_day + 1}天")
        print(f"{'='*60}")
        
        try:
            metrics.status = TurnStatus.RUNNING
            
            # 使用信号量控制并发
            semaphore = asyncio.Semaphore(self.max_concurrency)
            
            async def run_with_semaphore(task, task_id):
                async with semaphore:
                    try:
                        result = await asyncio.wait_for(task(), timeout=self.turn_timeout)
                        metrics.success_count += 1
                        return (task_id, "success", result)
                    except asyncio.TimeoutError:
                        metrics.status = TurnStatus.TIMEOUT
                        return (task_id, "timeout", None)
                    except Exception as e:
                        return (task_id, "error", str(e))
            
            # 并发执行所有NPC任务
            tasks = [
                run_with_semaphore(task, i) 
                for i, task in enumerate(npc_tasks)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            for result in results:
                if isinstance(result, tuple):
                    task_id, status, data = result
                    if status == "error":
                        metrics.fallback_count += 1
            
            metrics.status = TurnStatus.COMPLETED
            
        except Exception as e:
            print(f"回合执行失败: {e}")
            metrics.status = TurnStatus.FAILED
        
        finally:
            metrics.end_time = time.time()
            self.history.append(metrics)
        
        # 输出统计
        elapsed = metrics.elapsed_time
        print(f"\n回合耗时: {elapsed:.2f}秒")
        print(f"  成功: {metrics.success_count}/{metrics.npc_count}")
        print(f"  回退: {metrics.fallback_count}")
        
        # 进度回调
        if progress_callback:
            progress = turn_number / self.total_turns * 100
            await progress_callback({
                "turn": turn_number,
                "total": self.total_turns,
                "progress": progress,
                "elapsed": elapsed,
                "metrics": metrics
            })
        
        return metrics
    
    async def run_simulation(
        self,
        task_generator: Callable[[int], List[Callable]],
        progress_callback: Optional[Callable] = None,
        early_stop: Optional[Callable[[int, TurnMetrics], bool]] = None
    ) -> Dict[str, Any]:
        """
        运行完整模拟
        
        Args:
            task_generator: 任务生成器，接收回合编号返回NPC任务列表
            progress_callback: 进度回调
            early_stop: 提前停止条件
            
        Returns:
            模拟结果统计
        """
        self._running = True
        self._paused = False
        self.current_turn = 0
        
        results = {
            "total_turns": 0,
            "completed_turns": 0,
            "failed_turns": 0,
            "total_elapsed": 0.0,
            "avg_turn_time": 0.0
        }
        
        try:
            while self.current_turn < self.total_turns and self._running:
                # 检查暂停
                while self._paused:
                    await asyncio.sleep(0.1)
                
                self.current_turn += 1
                results["total_turns"] = self.current_turn
                
                # 生成回合任务
                npc_tasks = task_generator(self.current_turn)
                
                # 执行回合
                metrics = await self.run_turn(
                    self.current_turn,
                    npc_tasks,
                    progress_callback
                )
                
                if metrics.status == TurnStatus.COMPLETED:
                    results["completed_turns"] += 1
                else:
                    results["failed_turns"] += 1
                
                results["total_elapsed"] += metrics.elapsed_time
                
                # 提前停止检查
                if early_stop and early_stop(self.current_turn, metrics):
                    print(f"\n提前停止于回合 {self.current_turn}")
                    break
                    
        finally:
            self._running = False
        
        # 计算平均时间
        if results["completed_turns"] > 0:
            results["avg_turn_time"] = results["total_elapsed"] / results["completed_turns"]
        
        return results
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        if not self.history:
            return {}
        
        completed = [m for m in self.history if m.status == TurnStatus.COMPLETED]
        
        return {
            "total_turns": len(self.history),
            "completed": len(completed),
            "failed": len(self.history) - len(completed),
            "avg_turn_time": sum(m.elapsed_time for m in completed) / len(completed) if completed else 0,
            "max_turn_time": max((m.elapsed_time for m in completed), default=0),
            "total_success_rate": sum(m.success_count for m in completed) / sum(m.npc_count for m in completed) if completed else 0
        }

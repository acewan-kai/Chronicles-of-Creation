"""
A01 NPC动作执行器
负责调用LLM生成动作、解析结果、更新状态
"""

import asyncio
import time
import json
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from abc import ABC, abstractmethod

from openai import AsyncOpenAI, RateLimitError, APIError


@dataclass
class ActionResult:
    """动作执行结果"""
    actor_id: str
    actor_name: str
    action: str = ""
    target: Optional[str] = None
    target_id: Optional[str] = None
    location: str = ""
    action_type: str = "normal"  # normal, interaction, story_moment
    elapsed_time: float = 0.0
    status: str = "success"  # success, fallback, error
    raw_response: Optional[str] = None
    error: Optional[str] = None


class BaseLLMClient(ABC):
    """LLM客户端抽象基类"""
    
    @abstractmethod
    async def generate(self, messages: List[Dict], **kwargs) -> Optional[str]:
        """生成回复"""
        pass


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API客户端"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        temperature: float = 0.8,
        max_tokens: int = 300,
        top_p: float = 0.9,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def generate(self, messages: List[Dict], **kwargs) -> Optional[str]:
        """调用DeepSeek API生成回复"""
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    top_p=kwargs.get("top_p", self.top_p),
                )
                return response.choices[0].message.content.strip()
                
            except RateLimitError:
                if attempt < self.max_retries - 1:
                    print(f"API速率限制，等待{self.retry_delay}秒后重试...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    return None
                    
            except APIError as e:
                if attempt < self.max_retries - 1:
                    print(f"API错误: {e}，重试中...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    return None
        
        return None


class OpenAIClient(BaseLLMClient):
    """OpenAI API客户端"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        temperature: float = 0.8,
        max_tokens: int = 300,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def generate(self, messages: List[Dict], **kwargs) -> Optional[str]:
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=kwargs.get("model", self.model),
                    messages=messages,
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return None
        return None


class MockLLMClient(BaseLLMClient):
    """模拟LLM客户端（用于测试）"""
    
    MOCK_RESPONSES = [
        "站在院中远眺海面，思考着近日的异象",
        "在茶馆中品茶，观察周围人的言行举止",
        "与村民闲聊，旁敲侧击地打听村中的历史",
        "独自在村中巡视，检查各处是否一切正常",
        "整理物品，准备接下来的行动",
    ]
    
    async def generate(self, messages: List[Dict], **kwargs) -> Optional[str]:
        """返回模拟回复"""
        import random
        await asyncio.sleep(0.1)  # 模拟延迟
        return random.choice(self.MOCK_RESPONSES)


class ActionExecutor:
    """
    NPC动作执行器
    负责：生成动作 -> 解析结果 -> 更新状态
    """
    
    # 动作解析正则
    ACTION_PATTERN = re.compile(r'^(.+?)[:：]\s*(.+?)(?:\s*→\s*影响\s*(.+?))?$')
    
    def __init__(
        self,
        llm_client: BaseLLMClient,
        name_resolver: Optional[Dict[str, str]] = None
    ):
        self.llm_client = llm_client
        self.name_resolver = name_resolver or {}  # npc_id -> name
    
    def set_name_resolver(self, resolver: Dict[str, str]):
        """设置名称解析器"""
        self.name_resolver = resolver
    
    def resolve_name(self, npc_id: str) -> str:
        """解析NPC名称"""
        return self.name_resolver.get(npc_id, npc_id)
    
    async def execute(
        self,
        npc_id: str,
        system_prompt: str,
        user_prompt: str,
        **llm_kwargs
    ) -> ActionResult:
        """
        执行单个NPC动作
        
        Args:
            npc_id: NPC ID
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **llm_kwargs: 额外LLM参数
            
        Returns:
            ActionResult: 执行结果
        """
        start_time = time.time()
        result = ActionResult(
            actor_id=npc_id,
            actor_name=self.resolve_name(npc_id)
        )
        
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 调用LLM
        response = await self.llm_client.generate(messages, **llm_kwargs)
        result.elapsed_time = time.time() - start_time
        
        if response:
            result.raw_response = response
            # 解析动作
            parsed = self.parse_action(response, result.actor_name)
            result.action = parsed.get("action", response)
            result.target = parsed.get("target")
            result.action_type = self._classify_action(result.action, result.target)
            result.status = "success"
        else:
            # 回退到默认动作
            result.action = "保持沉默，观望周围动静"
            result.status = "fallback"
        
        return result
    
    def parse_action(self, response: str, actor_name: str) -> Dict[str, Any]:
        """
        解析LLM返回的动作
        
        支持格式：
        - "角色名: 动作描述 → 影响 目标"
        - "角色名：动作描述 → 影响 目标"
        - 纯动作描述
        """
        # 尝试匹配标准格式
        match = self.ACTION_PATTERN.match(response)
        if match:
            return {
                "actor": match.group(1).strip(),
                "action": match.group(2).strip(),
                "target": match.group(3).strip() if match.group(3) else None
            }
        
        # 尝试提取动作和目标
        if "→" in response:
            parts = response.split("→", 1)
            action = parts[0].strip()
            target = parts[1].strip() if len(parts) > 1 else None
            return {"action": action, "target": target}
        
        return {"action": response.strip(), "target": None}
    
    def _classify_action(self, action: str, target: Optional[str]) -> str:
        """
        分类动作类型
        
        Returns:
            - "story_moment": 有故事感的时刻
            - "interaction": 跨角色互动
            - "normal": 普通动作
        """
        # 有目标 = 互动
        if target:
            # 有情感词汇 = 故事感
            emotional_words = ["叹息", "悲伤", "喜悦", "愤怒", "思念", "犹豫", "坚定", "微笑", "泪", "心"]
            if any(word in action for word in emotional_words):
                return "story_moment"
            return "interaction"
        
        # 检查故事感关键词
        story_keywords = ["忽然", "突然", "回想起", "仿佛", "似乎", "注定", "命运"]
        if any(keyword in action for keyword in story_keywords):
            return "story_moment"
        
        return "normal"
    
    async def batch_execute(
        self,
        tasks: List[Dict[str, str]],
        **llm_kwargs
    ) -> List[ActionResult]:
        """
        批量执行动作
        
        Args:
            tasks: 任务列表，每项包含 npc_id, system_prompt, user_prompt
            
        Returns:
            结果列表
        """
        async def execute_task(task):
            return await self.execute(
                task["npc_id"],
                task["system_prompt"],
                task["user_prompt"],
                **llm_kwargs
            )
        
        results = await asyncio.gather(
            *[execute_task(t) for t in tasks],
            return_exceptions=True
        )
        
        return [
            r if isinstance(r, ActionResult) 
            else ActionResult(actor_id="unknown", actor_name="unknown", action="", status="error", error=str(r))
            for r in results
        ]

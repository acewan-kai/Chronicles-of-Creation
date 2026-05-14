"""
多LLM客户端统一接口
支持: DeepSeek / OpenAI / Kimi / MiniMax / 智谱GLM / 通义千问 / 混元 / 豆包 / OpenAI兼容
"""

import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

from openai import AsyncOpenAI, APIError, RateLimitError


class LLMProvider(Enum):
    """支持的LLM提供商"""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    KIMI = "kimi"           # Moonshot AI
    MINIMAX = "minimax"
    ZHIPU = "zhipu"         # 智谱GLM
    QWEN = "qwen"          # 通义千问
    HUNYUAN = "hunyuan"     # 腾讯混元
    DOUBAO = "doubao"       # 字节豆包
    CUSTOM = "custom"       # OpenAI兼容自定义
    MOCK = "mock"


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: LLMProvider
    api_key: str
    base_url: str
    model: str
    max_tokens: int = 300
    temperature: float = 0.8
    max_retries: int = 3
    retry_delay: float = 2.0


# 各大模型默认配置
DEFAULT_CONFIGS = {
    LLMProvider.DEEPSEEK: {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    LLMProvider.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    LLMProvider.KIMI: {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    LLMProvider.MINIMAX: {
        "base_url": "https://api.minimax.chat/v1",
        "model": "abab6-chat",
    },
    LLMProvider.ZHIPU: {
        "base_url": "https://open.bigmodel.cn/v1",
        "model": "glm-4-flash",
    },
    LLMProvider.QWEN: {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-turbo",
    },
    LLMProvider.HUNYUAN: {
        "base_url": "https://api.hunyuan.cloud.tencent.com",
        "model": "hunyuan",
    },
    LLMProvider.DOUBAO: {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-32k",
    },
    LLMProvider.CUSTOM: {
        "base_url": "",
        "model": "gpt-4o-mini",
    },
}


class BaseLLMClient:
    """LLM客户端基类"""

    async def generate(self, messages: List[Dict], **kwargs) -> Optional[str]:
        raise NotImplementedError


class MultiLLMClient(BaseLLMClient):
    """
    多LLM统一客户端

    支持provider:
    - deepseek: DeepSeek系列
    - openai: OpenAI官方
    - kimi: Moonshot AI (Kimi)
    - minimax: MiniMax
    - zhipu: 智谱GLM
    - qwen: 通义千问
    - hunyuan: 腾讯混元
    - doubao: 字节豆包
    - custom: OpenAI兼容自定义端点
    """

    PROVIDER_ALIASES = {
        # 小米/小爱 (可能指小爱同学背后的模型)
        "xiaomi": LLMProvider.DEEPSEEK,
        "xiaoai": LLMProvider.DEEPSEEK,
        "minilm": LLMProvider.DEEPSEEK,
        # Kimi
        "kimi": LLMProvider.KIMI,
        "moonshot": LLMProvider.KIMI,
        "moonshotai": LLMProvider.KIMI,
        # MiniMax
        "minimax": LLMProvider.MINIMAX,
        "abab": LLMProvider.MINIMAX,
        # 智谱
        "zhipu": LLMProvider.ZHIPU,
        "glm": LLMProvider.ZHIPU,
        "bigmodel": LLMProvider.ZHIPU,
        # 通义千问
        "qwen": LLMProvider.QWEN,
        "tongyi": LLMProvider.QWEN,
        "aliyun": LLMProvider.QWEN,
        "alibaba": LLMProvider.QWEN,
        # 腾讯混元
        "hunyuan": LLMProvider.HUNYUAN,
        "tencent": LLMProvider.HUNYUAN,
        "tencenthunyuan": LLMProvider.HUNYUAN,
        # 字节豆包
        "doubao": LLMProvider.DOUBAO,
        "bytedance": LLMProvider.DOUBAO,
        "volcengine": LLMProvider.DOUBAO,
        # DeepSeek
        "deepseek": LLMProvider.DEEPSEEK,
        "deepseekv3": LLMProvider.DEEPSEEK,
        # OpenAI
        "openai": LLMProvider.OPENAI,
        "gpt": LLMProvider.OPENAI,
        # Custom
        "custom": LLMProvider.CUSTOM,
        "openai-compatible": LLMProvider.CUSTOM,
        "compatible": LLMProvider.CUSTOM,
    }

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[AsyncOpenAI] = None
        self._init_client()

    def _init_client(self):
        """初始化OpenAI兼容客户端"""
        if self.config.provider == LLMProvider.MOCK:
            return

        self._client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

    @property
    def provider_name(self) -> str:
        return self.config.provider.value

    @property
    def model_name(self) -> str:
        return self.config.model

    async def generate(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Optional[str]:
        """调用LLM生成回复"""
        if self.config.provider == LLMProvider.MOCK:
            import random
            await asyncio.sleep(0.1)
            responses = [
                "站在院中远眺海面，思考着近日的异象",
                "在茶馆中品茶，观察周围人的言行举止",
                "与村民闲聊，旁敲侧击地打听村中的历史",
            ]
            return random.choice(responses)

        if not self._client:
            return None

        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    **kwargs
                )
                return response.choices[0].message.content.strip()

            except RateLimitError:
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    return None

            except APIError as e:
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    print(f"[MultiLLM] API error: {e}")
                    return None

        return None


class LLMClientFactory:
    """LLM客户端工厂"""

    # 环境变量名映射
    ENV_KEYS = {
        LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
        LLMProvider.OPENAI: "OPENAI_API_KEY",
        LLMProvider.KIMI: "KIMI_API_KEY",
        LLMProvider.MINIMAX: "MINIMAX_API_KEY",
        LLMProvider.ZHIPU: "ZHIPU_API_KEY",
        LLMProvider.QWEN: "QWEN_API_KEY",
        LLMProvider.HUNYUAN: "HUNYUAN_API_KEY",
        LLMProvider.DOUBAO: "DOUBAO_API_KEY",
        LLMProvider.CUSTOM: "CUSTOM_API_KEY",
    }

    # base_url环境变量名
    BASE_URL_KEYS = {
        LLMProvider.DEEPSEEK: "DEEPSEEK_BASE_URL",
        LLMProvider.OPENAI: "OPENAI_BASE_URL",
        LLMProvider.KIMI: "KIMI_BASE_URL",
        LLMProvider.MINIMAX: "MINIMAX_BASE_URL",
        LLMProvider.ZHIPU: "ZHIPU_BASE_URL",
        LLMProvider.QWEN: "QWEN_BASE_URL",
        LLMProvider.HUNYUAN: "HUNYUAN_BASE_URL",
        LLMProvider.DOUBAO: "DOUBAO_BASE_URL",
        LLMProvider.CUSTOM: "CUSTOM_BASE_URL",
    }

    # model环境变量名
    MODEL_KEYS = {
        LLMProvider.DEEPSEEK: "DEEPSEEK_MODEL",
        LLMProvider.OPENAI: "OPENAI_MODEL",
        LLMProvider.KIMI: "KIMI_MODEL",
        LLMProvider.MINIMAX: "MINIMAX_MODEL",
        LLMProvider.ZHIPU: "ZHIPU_MODEL",
        LLMProvider.QWEN: "QWEN_MODEL",
        LLMProvider.HUNYUAN: "HUNYUAN_MODEL",
        LLMProvider.DOUBAO: "DOUBAO_MODEL",
        LLMProvider.CUSTOM: "CUSTOM_MODEL",
    }

    def __init__(self, env_dict: Optional[Dict[str, str]] = None):
        import os
        self.env = env_dict or os.environ

    def _get_env(self, key: str, default: str = "") -> str:
        return self.env.get(key, default)

    def resolve_provider(self, mode: str) -> Optional[LLMProvider]:
        """解析provider名称（支持别名）"""
        mode_lower = mode.lower().strip()

        # 直接匹配
        for provider in LLMProvider:
            if provider.value == mode_lower:
                return provider

        # 别名匹配
        if mode_lower in MultiLLMClient.PROVIDER_ALIASES:
            return MultiLLMClient.PROVIDER_ALIASES[mode_lower]

        return None

    def create(
        self,
        mode: str = "auto",
        default_temperature: float = 0.8,
        default_max_tokens: int = 300,
    ) -> tuple[BaseLLMClient, str]:
        """
        创建LLM客户端

        Args:
            mode: provider名称，支持别名
                常用: deepseek / openai / kimi / minimax / zhipu / qwen / hunyuan / doubao / custom / mock / auto
                别名: xiaomi, xiaoai → deepseek; moonshot → kimi; glm → zhipu; qwen → qwen; etc.
            default_temperature: 默认温度
            default_max_tokens: 默认最大token数

        Returns:
            (client, provider_name)
        """
        # Mock模式
        if mode == "mock":
            return MultiLLMClient(LLMConfig(
                provider=LLMProvider.MOCK,
                api_key="",
                base_url="",
                model="mock",
            )), "mock"

        # 解析provider
        provider = self.resolve_provider(mode)
        if not provider:
            print(f"[LLMFactory] Unknown provider '{mode}', using mock")
            return MultiLLMClient(LLMConfig(
                provider=LLMProvider.MOCK,
                api_key="",
                base_url="",
                model="mock",
            )), "mock"

        # 获取API Key
        env_key = self.ENV_KEYS.get(provider, f"{provider.value.upper()}_API_KEY")
        api_key = self._get_env(env_key)

        if not api_key:
            print(f"[LLMFactory] {env_key} not found, using mock")
            return MultiLLMClient(LLMConfig(
                provider=LLMProvider.MOCK,
                api_key="",
                base_url="",
                model="mock",
            )), "mock"

        # 获取base_url
        base_url_key = self.BASE_URL_KEYS.get(provider)
        base_url = self._get_env(base_url_key, "") if base_url_key else ""
        if not base_url:
            base_url = DEFAULT_CONFIGS[provider]["base_url"]

        # 获取model
        model_key = self.MODEL_KEYS.get(provider)
        model = self._get_env(model_key, "") if model_key else ""
        if not model:
            model = DEFAULT_CONFIGS[provider]["model"]

        # 创建客户端
        config = LLMConfig(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=default_temperature,
            max_tokens=default_max_tokens,
        )

        client = MultiLLMClient(config)
        print(f"[LLMFactory] Created {provider.value} client (model={model})")

        return client, provider.value

    def create_auto(self) -> tuple[BaseLLMClient, str]:
        """
        自动选择可用provider（按优先级）

        优先级: DeepSeek > Kimi > OpenAI > 其他
        """
        # 按优先级尝试
        priority = [
            LLMProvider.DEEPSEEK,
            LLMProvider.KIMI,
            LLMProvider.MINIMAX,
            LLMProvider.ZHIPU,
            LLMProvider.QWEN,
            LLMProvider.OPENAI,
        ]

        for provider in priority:
            env_key = self.ENV_KEYS[provider]
            api_key = self._get_env(env_key)
            if api_key:
                return self.create(provider.value)

        print("[LLMFactory] No API key found, using mock")
        return self.create("mock")


# 兼容旧接口
DeepSeekClient = OpenAIClient = None  # 保留导入兼容性


def create_multi_llm_client(mode: str = "auto") -> tuple[Any, str]:
    """便捷函数：创建多LLM客户端"""
    factory = LLMClientFactory()
    return factory.create(mode)
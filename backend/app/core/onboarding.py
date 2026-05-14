"""
用户引导流程模块
5步以内从注册到首个世界运行
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Callable
from enum import Enum


class GuideStep(Enum):
    """引导步骤枚举"""
    WELCOME = "welcome"
    CHOOSE_TEMPLATE = "choose_template"
    NAME_YOUR_WORLD = "name_your_world"
    CUSTOMIZE_CHARACTERS = "customize_characters"
    START_SIMULATION = "start_simulation"


@dataclass
class GuideState:
    """引导流程状态"""
    current_step: GuideStep = GuideStep.WELCOME
    selected_template: Optional[str] = None
    world_name: Optional[str] = None
    customized_npcs: List[dict] = field(default_factory=list)
    completed: bool = False
    
    # 用户配置
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class GuideStepConfig:
    """引导步骤配置"""
    step: GuideStep
    title: str
    description: str
    prompt: str
    options: Optional[List[str]] = None
    validation: Optional[Callable[[str], bool]] = None
    error_message: str = "输入无效，请重试"


class OnboardingGuide:
    """
    新用户引导流程
    
    5步引导：
    1. 欢迎 - 介绍平台
    2. 选择模板 - 3个预制世界
    3. 命名世界 - 用户命名
    4. 自定义角色（可选）- 调整NPC
    5. 启动模拟 - 开始运行
    """
    
    TEMPLATES = {
        "cultivation": {
            "id": "cultivation",
            "name": "青云仙门",
            "genre": "修仙",
            "description": "以剑道闻名的修仙门派，弟子们为突破境界而苦修",
            "thumbnail": "🗡️",
            "difficulty": "入门"
        },
        "wuxia": {
            "id": "wuxia",
            "name": "江湖风云录",
            "genre": "武侠",
            "description": "明末乱世，门派林立，一把传说中的绝世神兵引发争夺",
            "thumbnail": "🌙",
            "difficulty": "入门"
        },
        "urban": {
            "id": "urban",
            "name": "深夜事务所",
            "genre": "都市奇幻",
            "description": "现代都市中隐藏着无数神秘存在，承接超自然委托",
            "thumbnail": "🌃",
            "difficulty": "入门"
        }
    }
    
    def __init__(self):
        self.state = GuideState()
        self._steps_config = self._build_steps_config()
    
    def _build_steps_config(self) -> dict:
        """构建引导步骤配置"""
        return {
            GuideStep.WELCOME: GuideStepConfig(
                step=GuideStep.WELCOME,
                title="欢迎来到AI小说创作平台",
                description="在这里，AI角色将在你构建的世界中自主生活、互动，\n"
                           "故事将从他们的行动中自然涌现。",
                prompt="准备好了吗？输入任意内容开始创作你的第一个世界。",
                options=["🚀 开始创作", "了解更多"]
            ),
            GuideStep.CHOOSE_TEMPLATE: GuideStepConfig(
                step=GuideStep.CHOOSE_TEMPLATE,
                title="选择你的世界模板",
                description="我们提供了3个精心设计的预制世界，你也可以从零开始创建。",
                prompt="请选择一个模板（输入数字）：\n"
                       "1. 🗡️ 青云仙门（修仙）\n"
                       "2. 🌙 江湖风云录（武侠）\n"
                       "3. 🌃 深夜事务所（都市奇幻）",
                options=["1", "2", "3"],
                validation=self._validate_template_choice,
                error_message="请输入 1、2 或 3"
            ),
            GuideStep.NAME_YOUR_WORLD: GuideStepConfig(
                step=GuideStep.NAME_YOUR_WORLD,
                title="为你的世界命名",
                description="给你的世界起一个独一无二的名字，\n"
                           "这将成为故事发生的舞台。",
                prompt="请输入世界名称（2-20个字符）：",
                validation=self._validate_world_name,
                error_message="名称长度需在2-20个字符之间"
            ),
            GuideStep.CUSTOMIZE_CHARACTERS: GuideStepConfig(
                step=GuideStep.CUSTOMIZE_CHARACTERS,
                title="自定义角色（可选）",
                description="你可以调整预置角色的性格、背景或关系，\n"
                           "也可以保持默认设置直接开始。",
                prompt="选择操作：\n"
                       "1. 保持默认设置，直接开始\n"
                       "2. 调整某个角色的设定\n"
                       "3. 添加新角色",
                options=["1", "2", "3"],
                validation=lambda x: x in ["1", "2", "3"]
            ),
            GuideStep.START_SIMULATION: GuideStepConfig(
                step=GuideStep.START_SIMULATION,
                title="启动模拟",
                description="一切准备就绪！\n"
                           "AI角色们将在你的世界中开始他们的故事。",
                prompt="输入 '开始' 启动模拟：",
                validation=lambda x: x.strip() in ["开始", "start", "Start"],
                error_message="请输入 '开始' 来启动模拟"
            )
        }
    
    @staticmethod
    def _validate_template_choice(value: str) -> bool:
        """验证模板选择"""
        return value.strip() in ["1", "2", "3"]
    
    @staticmethod
    def _validate_world_name(value: str) -> bool:
        """验证世界名称"""
        name = value.strip()
        if len(name) < 2 or len(name) > 20:
            return False
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$', name):
            return False
        return True
    
    def get_current_step_info(self) -> GuideStepConfig:
        """获取当前步骤信息"""
        return self._steps_config[self.state.current_step]
    
    def process_input(self, user_input: str) -> dict:
        """
        处理用户输入
        
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "next_step": Optional[GuideStep],
                "data": Optional[dict]
            }
        """
        step_config = self.get_current_step_info()
        
        # 验证输入
        if step_config.validation and not step_config.validation(user_input):
            return {
                "success": False,
                "message": step_config.error_message,
                "next_step": None,
                "data": None
            }
        
        # 根据步骤处理输入
        if self.state.current_step == GuideStep.WELCOME:
            self.state.current_step = GuideStep.CHOOSE_TEMPLATE
            
        elif self.state.current_step == GuideStep.CHOOSE_TEMPLATE:
            template_map = {"1": "cultivation", "2": "wuxia", "3": "urban"}
            self.state.selected_template = template_map[user_input.strip()]
            self.state.current_step = GuideStep.NAME_YOUR_WORLD
            
        elif self.state.current_step == GuideStep.NAME_YOUR_WORLD:
            self.state.world_name = user_input.strip()
            self.state.current_step = GuideStep.CUSTOMIZE_CHARACTERS
            
        elif self.state.current_step == GuideStep.CUSTOMIZE_CHARACTERS:
            if user_input.strip() == "1":
                # 保持默认设置
                self.state.current_step = GuideStep.START_SIMULATION
            else:
                # TODO: 实现角色自定义逻辑
                self.state.current_step = GuideStep.START_SIMULATION
                
        elif self.state.current_step == GuideStep.START_SIMULATION:
            self.state.completed = True
        
        return {
            "success": True,
            "message": "已完成",
            "next_step": self.state.current_step if not self.state.completed else None,
            "data": self._get_completion_data()
        }
    
    def _get_completion_data(self) -> dict:
        """获取完成时的数据"""
        template = self.TEMPLATES.get(self.state.selected_template, {})
        return {
            "world_name": self.state.world_name,
            "template": self.state.selected_template,
            "template_name": template.get("name", ""),
            "npcs": self.state.customized_npcs or "default",
            "ready_to_start": self.state.completed
        }
    
    def get_progress(self) -> dict:
        """获取当前进度"""
        steps = list(GuideStep)
        current_index = steps.index(self.state.current_step)
        return {
            "current_step": self.state.current_step.value,
            "step_number": current_index + 1,
            "total_steps": len(steps),
            "progress_percent": int((current_index / len(steps)) * 100)
        }
    
    def reset(self):
        """重置引导流程"""
        self.state = GuideState()
    
    @classmethod
    def get_available_templates(cls) -> List[dict]:
        """获取可用模板列表"""
        return list(cls.TEMPLATES.values())
    
    @classmethod
    def get_template_detail(cls, template_id: str) -> Optional[dict]:
        """获取模板详情"""
        return cls.TEMPLATES.get(template_id)


# 快捷函数
def create_guide() -> OnboardingGuide:
    """创建新的引导实例"""
    return OnboardingGuide()

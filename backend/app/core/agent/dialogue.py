"""
C03 智能体对话系统
NPC间的自然语言交互与记忆写入
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from .agent import Agent, MemoryType
    from ..sandbox.action_executor import BaseLLMClient


# ═══════════════════════════════════════════════════════════
# 对话意图分类
# ═══════════════════════════════════════════════════════════

class DialogueIntent(Enum):
    """对话意图"""
    CASUAL = "casual"           # 闲聊
    NEGOTIATION = "negotiation" # 谈判
    TRICKERY = "trickery"       # 欺骗
    INTIMIDATION = "intimidation" # 威胁
    ALLIANCE = "alliance"       # 结盟
    BETRAYAL = "betrayal"       # 背叛
    TRUTH_REVEAL = "truth_reveal" # 揭露真相
    QUESTION = "question"        # 询问
    ANSWER = "answer"           # 回答
    CHALLENGE = "challenge"     # 挑战
    FAREWELL = "farewell"       # 告别


# 意图关键词映射
INTENT_KEYWORDS = {
    DialogueIntent.NEGOTIATION: ["谈判", "商量", "交易", "条件", "让步", "妥协", "协议"],
    DialogueIntent.INTIMIDATION: ["威胁", "警告", "小心", "别", "否则", "后果"],
    DialogueIntent.ALLIANCE: ["结盟", "合作", "联手", "一起", "共同", "盟友", "同盟"],
    DialogueIntent.BETRAYAL: ["背叛", "出卖", "告密"],
    DialogueIntent.TRUTH_REVEAL: ["揭露", "揭穿", "发现", "真相", "其实", "秘密"],
    DialogueIntent.QUESTION: ["问", "打听", "谁", "什么", "为什么", "如何", "怎么"],
    DialogueIntent.ANSWER: ["回答", "解释", "说", "因为", "是的", "没错"],
    DialogueIntent.CHALLENGE: ["挑战", "不服", "比试", "较量", "对战"],
    DialogueIntent.FAREWELL: ["告别", "离开", "告辞", "走了", "后会有期"],
}


@dataclass
class DialogueTurn:
    """对话轮次"""
    turn_index: int
    speaker_id: str
    speaker_name: str
    content: str
    intent: DialogueIntent = DialogueIntent.CASUAL
    emotion: str = ""  # 情感标签


@dataclass
class Dialogue:
    """完整对话"""
    dialogue_id: str
    speaker_a: str  # agent_id
    speaker_a_name: str
    speaker_b: str  # agent_id
    speaker_b_name: str
    turns: List[DialogueTurn] = field(default_factory=list)
    location: str = ""
    topic: str = ""  # 对话主题
    outcome: str = ""  # 对话结果/影响
    max_turns: int = 8


# ═══════════════════════════════════════════════════════════
# 对话生成Prompt
# ═══════════════════════════════════════════════════════════

DIALOGUE_SYSTEM_PROMPT = """你是一个角色扮演对话生成器。根据给定的情境和角色设定，生成两个角色之间的自然对话。

规则：
- 对话要符合角色性格（身份、性格、说话方式）
- 每轮对话简洁有力，2-4句话
- 使用「」作为对话引号
- 对话要有推进感，不能只是寒暄
- 检测对话意图：闲聊/谈判/欺骗/威胁/结盟/揭露/询问等

输出格式：
[INTENT:意图]speaker_name: 对话内容
[INTENT:意图]speaker_name: 对话内容

示例：
[INTENT:negotiation]清虚真人: 此次灵泉异动，恐有蹊跷。
[INTENT:question]明月师姐: 师父的意思是？
[INTENT:truth_reveal]清虚真人: 我怀疑魔教已在暗中渗透。"""


DIALOGUE_USER_PROMPT_TEMPLATE = """情境：
{context}

角色A：{speaker_a_name}
- 身份：{speaker_a_identity}
- 性格：{speaker_a_personality}

角色B：{speaker_b_name}
- 身份：{speaker_b_identity}
- 性格：{speaker_b_personality}

请生成角色A和角色B之间关于「{topic}」的对话，共{max_turns}轮。

要求：
- 对话要推动剧情发展
- 每方各{turns_per_side}轮
- 对话内容写入双方记忆流"""


# ═══════════════════════════════════════════════════════════
# 对话管理器
# ═══════════════════════════════════════════════════════════

class DialogueManager:
    """
    智能体对话管理器

    核心功能：
    1. 生成NPC间的自然语言对话
    2. 对话写入双方记忆流
    3. 对话意图追踪
    """

    def __init__(
        self,
        max_dialogue_turns: int = 8,
        memory_importance: float = 0.7,
    ):
        self.max_dialogue_turns = max_dialogue_turns
        self.memory_importance = memory_importance

        # 对话历史：(agent_id, target_id) -> Dialogue
        self._dialogues: Dict[Tuple[str, str], Dialogue] = {}

    async def generate_dialogue(
        self,
        speaker_a: "Agent",
        speaker_b: "Agent",
        topic: str,
        context: str,
        llm_client: "BaseLLMClient",
        max_turns: int = 8,
    ) -> Dialogue:
        """
        生成两个NPC之间的对话

        Args:
            speaker_a: 发言方A
            speaker_b: 发言方B
            topic: 对话主题
            context: 情境上下文
            llm_client: LLM客户端
            max_turns: 最大对话轮数

        Returns:
            Dialogue: 完整对话对象
        """
        speaker_a_name = speaker_a.config.name
        speaker_b_name = speaker_b.config.name

        dialogue_id = f"dlg_{speaker_a.agent_id}_{speaker_b.agent_id}_{id(self)}"

        dialogue = Dialogue(
            dialogue_id=dialogue_id,
            speaker_a=speaker_a.agent_id,
            speaker_a_name=speaker_a_name,
            speaker_b=speaker_b.agent_id,
            speaker_b_name=speaker_b_name,
            topic=topic,
            max_turns=max_turns,
        )

        # 构建prompt
        turns_per_side = max_turns // 2
        user_prompt = DIALOGUE_USER_PROMPT_TEMPLATE.format(
            context=context,
            speaker_a_name=speaker_a_name,
            speaker_a_identity=speaker_a.config.identity,
            speaker_a_personality=speaker_a.config.personality,
            speaker_b_name=speaker_b_name,
            speaker_b_identity=speaker_b.config.identity,
            speaker_b_personality=speaker_b.config.personality,
            topic=topic,
            max_turns=max_turns,
            turns_per_side=turns_per_side,
        )

        messages = [
            {"role": "system", "content": DIALOGUE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await llm_client.generate(
                messages,
                temperature=0.8,
                max_tokens=1000,
            )

            if response:
                turns = self._parse_dialogue_response(
                    response, speaker_a.agent_id, speaker_b.agent_id,
                    speaker_a_name, speaker_b_name
                )
                dialogue.turns = turns

        except Exception as e:
            print(f"[DialogueManager] Generate failed: {e}")

        # 如果生成失败，使用fallback
        if not dialogue.turns:
            dialogue = self._create_fallback_dialogue(
                speaker_a, speaker_b, topic
            )

        # 推断对话主题和结果
        dialogue.topic = topic
        dialogue.outcome = self._infer_outcome(dialogue)

        # 存储对话
        key = (speaker_a.agent_id, speaker_b.agent_id)
        self._dialogues[key] = dialogue

        return dialogue

    def _parse_dialogue_response(
        self,
        response: str,
        speaker_a_id: str,
        speaker_b_id: str,
        speaker_a_name: str,
        speaker_b_name: str,
    ) -> List[DialogueTurn]:
        """解析LLM生成的对话响应"""
        turns = []
        turn_index = 0

        # 匹配 [INTENT:xxx]name: content 格式
        pattern = re.compile(r'\[INTENT:(\w+)\]\s*([^:]+):\s*(.+)')

        current_speaker = speaker_a_id
        current_speaker_name = speaker_a_name

        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue

            # 解析意图
            intent_match = pattern.match(line)
            if intent_match:
                intent_str = intent_match.group(1)
                name = intent_match.group(2).strip()
                content = intent_match.group(3).strip()

                # 确定发言者
                if name == speaker_a_name:
                    current_speaker = speaker_a_id
                    current_speaker_name = speaker_a_name
                else:
                    current_speaker = speaker_b_id
                    current_speaker_name = speaker_b_name

                # 解析意图
                try:
                    intent = DialogueIntent(intent_str.lower())
                except ValueError:
                    intent = DialogueIntent.CASUAL

                turns.append(DialogueTurn(
                    turn_index=turn_index,
                    speaker_id=current_speaker,
                    speaker_name=current_speaker_name,
                    content=content,
                    intent=intent,
                ))
                turn_index += 1

        return turns

    def _create_fallback_dialogue(
        self,
        speaker_a: "Agent",
        speaker_b: "Agent",
        topic: str,
    ) -> Dialogue:
        """创建降级对话（无LLM时）"""
        dialogue_id = f"dlg_{speaker_a.agent_id}_{speaker_b.agent_id}_fallback"

        return Dialogue(
            dialogue_id=dialogue_id,
            speaker_a=speaker_a.agent_id,
            speaker_a_name=speaker_a.config.name,
            speaker_b=speaker_b.agent_id,
            speaker_b_name=speaker_b.config.name,
            topic=topic,
            turns=[
                DialogueTurn(
                    turn_index=0,
                    speaker_id=speaker_a.agent_id,
                    speaker_name=speaker_a.config.name,
                    content=f"关于「{topic}」，你怎么看？",
                    intent=DialogueIntent.QUESTION,
                ),
                DialogueTurn(
                    turn_index=1,
                    speaker_id=speaker_b.agent_id,
                    speaker_name=speaker_b.config.name,
                    content="此事还需从长计议。",
                    intent=DialogueIntent.ANSWER,
                ),
            ],
            outcome="双方交换了初步意见",
        )

    def _infer_outcome(self, dialogue: Dialogue) -> str:
        """推断对话结果"""
        if not dialogue.turns:
            return "对话未能进行"

        last_turn = dialogue.turns[-1]
        last_intent = last_turn.intent

        outcome_map = {
            DialogueIntent.ALLIANCE: "双方达成初步共识",
            DialogueIntent.NEGOTIATION: "谈判进行中",
            DialogueIntent.BETRAYAL: "存在背叛行为",
            DialogueIntent.TRUTH_REVEAL: "真相被揭露",
            DialogueIntent.INTIMIDATION: "存在威胁行为",
            DialogueIntent.FAREWELL: "对话结束",
            DialogueIntent.CHALLENGE: "双方对峙",
            DialogueIntent.CASUAL: "普通对话",
        }

        return outcome_map.get(last_intent, "对话结束")

    def write_to_memory(
        self,
        dialogue: Dialogue,
        agent_a: "Agent",
        agent_b: "Agent",
        current_turn: int,
    ):
        """
        将对话写入双方记忆流

        对话内容作为观察记忆写入，标记为重要（importance=0.8）
        """
        if not dialogue.turns:
            return

        # 构建对话摘要
        turn_summaries = []
        for turn in dialogue.turns:
            summary = f"「{turn.speaker_name}」说：{turn.content}"
            turn_summaries.append(summary)

        dialogue_text = "\n".join(turn_summaries)

        # 构建完整记忆内容
        memory_content = (
            f"【与{dialogue.speaker_b_name}的对话】\n"
            f"主题：{dialogue.topic}\n"
            f"地点：{dialogue.location or '未知'}\n"
            f"结果：{dialogue.outcome}\n"
            f"对话记录：\n{dialogue_text}"
        )

        # 写入双方记忆
        from .agent import MemoryType

        agent_a.memory.set_turn(current_turn)
        agent_a.memory.add_reflection(
            memory_content,
            current_turn,
            importance=self.memory_importance,
        )

        # 对方视角的记忆
        memory_content_b = (
            f"【与{dialogue.speaker_a_name}的对话】\n"
            f"主题：{dialogue.topic}\n"
            f"结果：{dialogue.outcome}\n"
            f"对话记录：\n{dialogue_text}"
        )

        agent_b.memory.set_turn(current_turn)
        agent_b.memory.add_reflection(
            memory_content_b,
            current_turn,
            importance=self.memory_importance,
        )

    def classify_intent(self, text: str) -> DialogueIntent:
        """根据文本内容分类对话意图"""
        text_lower = text.lower()

        for intent, keywords in INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return intent

        return DialogueIntent.CASUAL

    def get_dialogue_history(
        self,
        agent_a_id: str,
        agent_b_id: str,
    ) -> Optional[Dialogue]:
        """获取两个Agent之间的历史对话"""
        key = (agent_a_id, agent_b_id)
        reverse_key = (agent_b_id, agent_a_id)

        return self._dialogues.get(key) or self._dialogues.get(reverse_key)

    def to_dict(self, dialogue: Dialogue) -> Dict[str, Any]:
        """转换为API响应格式"""
        return {
            "dialogue_id": dialogue.dialogue_id,
            "speaker_a": dialogue.speaker_a_name,
            "speaker_b": dialogue.speaker_b_name,
            "topic": dialogue.topic,
            "outcome": dialogue.outcome,
            "location": dialogue.location,
            "turns": [
                {
                    "index": t.turn_index,
                    "speaker": t.speaker_name,
                    "content": t.content,
                    "intent": t.intent.value,
                }
                for t in dialogue.turns
            ],
            "turn_count": len(dialogue.turns),
        }
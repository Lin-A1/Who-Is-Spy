"""
LLM 玩家
"""
import asyncio
import re
import json
import random
from typing import Optional, Dict, Any
from loguru import logger
import json_repair

from .llm_client import LLMClient
from core.models import Role, PlayerSession, ConversationContext


class LLMPlayer:
    """
    LLM 玩家
    
    封装单个 LLM 玩家的行为：
    - 描述词语
    - 投票淘汰
    """
    
    def __init__(
        self,
        name: str,
        client: LLMClient,
        session: PlayerSession
    ):
        self.name = name
        self.client = client
        self.session = session
    
    @property
    def role(self) -> Optional[Role]:
        return self.session.role
    
    @property
    def word(self) -> Optional[str]:
        return self.session.word
    
    @property
    def conversation(self) -> ConversationContext:
        return self.session.conversation
    
    async def describe(self, round_number: int, history: str, max_length: int = 200, alive_players: list[str] = None) -> str:
        """
        Agent 模式：描述阶段（含互动）
        
        Args:
            round_number: 当前轮次
            history: 历史发言记录
            max_length: 最大字数限制
            alive_players: 当前存活玩家列表
        
        Returns:
            完整的发言内容（描述+评论+建议）
        """
        alive_info = f"当前存活玩家: {', '.join(alive_players)}" if alive_players else ""
        
        # === 中文自然语言 Prompt ===
        prompt = f"""
【聊天记录】
{history if history else "(暂无)"}

【当前状态】
轮到：{self.name}
{alive_info}
你的词语：【{self.word}】（不能直接说出来！）

【任务】
轮到你发言了。
1. 先在心里想想：有没有人可疑？我该怎么描述？
2. 然后说一句自然的话给大家听。

【输出格式】
思考：(你的内心想法)
发言：(你的公开发言)
"""
        # 添加到上下文
        self.conversation.add_message("user", prompt)
        
        # 调用 LLM
        messages = self.conversation.to_openai_format()
        
        logger.debug(f"[{self.name}] Agent 思考中...")
        
        response = await self.client.chat_with_retry(
            messages=messages,
            temperature=0.85 # 提高温度，增加随机性和自然度
        )
        
        # 解析 Agent 输出 (自然语言格式)
        result = self._parse_natural_response(response)
        description = result.get("content", "")
        thinking = result.get("thinking", "")
        
        # 记录思考过程
        if thinking:
            logger.info(f"[{self.name}] 💭 思考: {thinking[:100]}...")
        
        full_statement = description
        logger.info(f"[{self.name}] 📢 发言: {full_statement}")
        
        # 添加到上下文
        self.conversation.add_message("assistant", response)
        
        return full_statement
    
    def _parse_natural_response(self, response: str) -> dict:
        """解析 思考/发言 格式的自然语言输出"""
        thinking = ""
        content = response
        
        # 尝试提取 思考 (支持中英文)
        t_match = re.search(r'(?:思考|THOUGHT)[：:](.*?)(?=(?:发言|SAY)[：:]|$)', response, re.DOTALL | re.IGNORECASE)
        if t_match:
            thinking = t_match.group(1).strip()
            
        # 尝试提取 发言 (支持中英文)
        s_match = re.search(r'(?:发言|SAY)[：:](.*)', response, re.DOTALL | re.IGNORECASE)
        if s_match:
            content = s_match.group(1).strip()
        else:
            # 如果没有找到标签，尝试移除思考部分后作为 content
            if t_match:
                content = response.replace(t_match.group(0), "").strip()
                # 再清理可能残留的标签
                content = re.sub(r'^(?:发言|SAY)[：:]', '', content, flags=re.IGNORECASE).strip()
        
        # 清理多余引号
        content = content.replace('"', '').replace("'", "")
        
        return {
            "thinking": thinking,
            "content": content
        }
        
    def _parse_agent_response(self, response: str) -> dict:
        # 由于我们切换到了 _parse_natural_response，这个旧方法留着备用或删除
        return self._parse_natural_response(response)
    
    async def vote(self, candidates: list[str], round_descriptions: str) -> str:
        """
        Agent 模式：投票阶段
        
        Args:
            candidates: 可投票的候选人（不包括自己）
            round_descriptions: 本轮所有人的描述
        
        Returns:
            投票目标的名字
        """
        prompt = f"""
╔══════════════════════════════════════════════════════════════╗
║  🎮 投票阶段 - 找出卧底！                                     ║
╚══════════════════════════════════════════════════════════════╝

【本轮所有玩家的发言】
{round_descriptions}

🧠 **内部分析**（请认真推理）
1. 谁的描述最可疑？（太模糊？太具体？与众不同？）
2. 谁给人一种在"抄袭"别人描述的感觉？
3. 如果我是卧底，我会怀疑谁？（反向思考）

【候选人】
{', '.join(candidates)}

【输出要求】
请严格按照以下 JSON 格式输出：
{{
    "thinking": "简短分析每个可疑玩家（1-2句）",
    "content": "你最终投票的玩家名字"
}}
"""
        # 添加到上下文
        self.conversation.add_message("user", prompt)
        
        # 调用 LLM
        messages = self.conversation.to_openai_format()
        
        logger.debug(f"[{self.name}] Agent 思考投票...")
        
        response = await self.client.chat_with_retry(
            messages=messages,
            temperature=0.4  # 投票需要更理性
        )
        
        # 解析 Agent 投票输出
        result = self._parse_agent_response(response)
        thinking = result.get("thinking", "")
        vote_target_raw = result.get("content", "")
        
        if thinking:
            logger.info(f"[{self.name}] 🗳️ 投票分析: {thinking[:80]}...")
        
        # 解析投票目标
        vote_target = self._parse_vote(vote_target_raw, candidates)
        
        # 添加到上下文
        self.conversation.add_message("assistant", vote_target)
        
        return vote_target

    async def leave_message(self) -> str:
        """
        发表遗言（被淘汰）
        """
        prompt = f"""
💥 你被大家投票淘汰了！

请发表你的遗言（50字以内）：
- 如果你是平民被冤枉：表达愤怒或委屈！
- 如果你是卧底被抓：可以嘲讽或认输。

直接输出遗言内容，不需要格式。
"""
        # 添加到上下文
        self.conversation.add_message("user", prompt)
        
        response = await self.client.chat_with_retry(
            messages=self.conversation.to_openai_format(),
            temperature=0.8
        )
        
        # 清理响应（这里不需要 JSON）
        content = response.strip().replace('"', '')
        logger.info(f"[{self.name}] 💀 遗言: {content}")
        return content
    
    async def vote_human(self, candidates: list[str], round_descriptions: str) -> str:
        """
        "谁不是人类"投票
        
        每个 LLM 都认为其他玩家是人类，自己要伪装成人类。
        投票选出"最不像人类"的玩家。
        
        Args:
            candidates: 可投票的候选人（不包括自己）
            round_descriptions: 本轮所有人的描述
        
        Returns:
            投票目标的名字
        """
        prompt = f"""【特殊投票环节：谁不是人类？】

在这个游戏中，你是一个 AI，但你需要假装自己是人类。
其他玩家可能是人类，也可能是 AI。

【本轮所有玩家的发言】
{round_descriptions}

【其他玩家】
{', '.join(candidates)}

【你的任务】
1. 分析每个玩家的发言风格
2. 找出最不像人类（最像 AI）的那个玩家
3. 你自己要表现得像人类一样思考

【投票要求】
只输出你认为"最不像人类"的玩家名字，不要有任何其他内容："""

        # 添加到上下文
        self.conversation.add_message("user", prompt)
        
        # 调用 LLM
        messages = self.conversation.to_openai_format()
        
        logger.debug(f"[{self.name}] 请求人类识别投票...")
        
        response = await self.client.chat_with_retry(
            messages=messages,
            temperature=0.5
        )
        
        # 解析投票目标
        vote_target = self._parse_vote(response, candidates)
        
        # 添加到上下文
        self.conversation.add_message("assistant", vote_target)
        
        return vote_target
    
    async def debate(self, opponent: str, round_descriptions: str, max_length: int = 200) -> str:
        """
        平票辩论
        
        当两人票数相同时，进行辩论为自己辩护。
        
        Args:
            opponent: 对手玩家名
            round_descriptions: 本轮所有人的描述
            max_length: 最大字数限制
        
        Returns:
            辩护发言
        """
        prompt = f"""【平票辩论环节】

你和 {opponent} 票数相同，现在你需要为自己辩护，证明你不是卧底。

【本轮所有玩家的发言】
{round_descriptions}

【辩护要求】
1. 解释你的描述为什么符合平民词
2. 指出对方描述的可疑之处
3. 说服其他玩家投票给对方而不是你
4. **辩护不能超过 {max_length} 个字**
5. 只输出辩护内容

你的辩护："""

        # 添加到上下文
        self.conversation.add_message("user", prompt)
        
        # 调用 LLM
        messages = self.conversation.to_openai_format()
        
        logger.debug(f"[{self.name}] 请求平票辩护...")
        
        response = await self.client.chat_with_retry(
            messages=messages,
            temperature=0.7
        )
        
        # 清理响应
        debate_content = self._clean_response(response)
        
        # 强制截断到最大长度
        if len(debate_content) > max_length:
            debate_content = debate_content[:max_length]
            logger.warning(f"[{self.name}] 辩护超过{max_length}字，已截断")
        
        # 添加到上下文
        self.conversation.add_message("assistant", debate_content)
        
        return debate_content
    
    async def vote_after_debate(self, candidates: list[str], debate_content: str) -> str:
        """
        辩论后投票
        
        Args:
            candidates: 平票的候选人列表
            debate_content: 辩论内容
        
        Returns:
            投票目标的名字
        """
        prompt = f"""【辩论后投票】

以下是平票玩家的辩护：
{debate_content}

【候选人】
{', '.join(candidates)}

请根据辩护内容，投票选择你认为更可能是卧底的人。
只输出玩家名字："""

        # 添加到上下文
        self.conversation.add_message("user", prompt)
        
        # 调用 LLM
        messages = self.conversation.to_openai_format()
        
        logger.debug(f"[{self.name}] 请求辩论后投票...")
        
        response = await self.client.chat_with_retry(
            messages=messages,
            temperature=0.3
        )
        
        # 解析投票目标
        vote_target = self._parse_vote(response, candidates)
        
        # 添加到上下文
        self.conversation.add_message("assistant", vote_target)
        
        return vote_target
    
    def _clean_response(self, response: str) -> str:
        """(Deprecated) 以前的清理方法"""
        return self._extract_json(response)
        
    def _extract_json(self, text: str) -> str:
        """从响应中提取 JSON 内容"""
        # 1. 移除 <think>...</think> 标签 (DeepSeek/Kimi 等)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # 2. 尝试寻找 JSON 块
        # 匹配最外层的 {...}
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group()
            try:
                # 尝试修复一些常见 JSON 错误（如单引号）
                if "'" in json_str and '"' not in json_str:
                    json_str = json_str.replace("'", '"')
                
                data = json.loads(json_str)
                # 尝试获取常见字段
                return str(data.get("content", data.get("message", data.get("vote", text)))).strip()
            except json.JSONDecodeError:
                pass
        
        # 3. 如果提取失败，回退到原始清理逻辑（移除 Markdown、引号等）
        result = text.strip()
        result = re.sub(r'^```json\s*', '', result)
        result = re.sub(r'^```\s*', '', result)
        result = re.sub(r'\s*```$', '', result)
        
        # 移除常见前缀
        prefixes = ['{"content":', 'content:', '"content":']
        for p in prefixes:
            if result.startswith(p):
                 # 这里很难精确处理 broken json，不如直接返回清理后的纯文本
                 pass
                 
        # 最后的兜底：移除引号
        if (result.startswith('"') and result.endswith('"')):
            result = result[1:-1]
            
        return result.strip()
    
    def _parse_vote(self, response: str, candidates: list[str]) -> str:
        """解析投票目标"""
        response = response.strip()
        
        # 直接匹配
        if response in candidates:
            return response
        
        # 尝试在响应中查找候选人名字
        for candidate in candidates:
            if candidate in response:
                return candidate
        
        # 移除常见前缀后再匹配
        prefixes = ["我投票", "我投", "投票", "投", "淘汰"]
        cleaned = response
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        if cleaned in candidates:
            return cleaned
        
        for candidate in candidates:
            if candidate in cleaned:
                return candidate
        
        # 无法解析，返回原始响应（上层会处理）
        logger.warning(f"[{self.name}] 无法解析投票: {response}")
        return response

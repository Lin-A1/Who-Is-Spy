"""
数据模型定义
"""
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class Role(Enum):
    """玩家角色"""
    CIVILIAN = "civilian"  # 平民
    SPY = "spy"  # 卧底


class GamePhase(Enum):
    """游戏阶段"""
    WAITING = "waiting"  # 等待开始
    INIT = "init"  # 初始化中
    DESCRIPTION = "description"  # 描述阶段
    VOTING = "voting"  # 投票阶段
    ELIMINATION = "elimination"  # 淘汰结算
    FINISHED = "finished"  # 游戏结束


class Message(BaseModel):
    """LLM 对话消息"""
    role: str  # "system" | "user" | "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConversationContext(BaseModel):
    """
    LLM 对话上下文 - 智能记忆管理
    
    记忆管理策略:
    1. 短期记忆: 保留最近的完整对话 (recent_messages_count 条)
    2. 长期记忆: 历史摘要 (用于保留重要信息但节省 token)
    3. 系统记忆: System prompt 始终保留
    4. 自动裁剪: 当 token 超限时,压缩历史
    """
    player_name: str
    messages: list[Message] = Field(default_factory=list)
    token_count: int = 0
    max_tokens: int = 8000  # 上下文窗口限制
    recent_messages_count: int = 20  # 保留最近的消息数
    
    # 长期记忆摘要
    memory_summary: str = ""
    
    def add_message(self, role: str, content: str) -> None:
        """添加消息"""
        self.messages.append(Message(role=role, content=content))
        self.token_count += len(content) // 3  # 中文字符估算
        self._manage_memory()
    
    def _manage_memory(self) -> None:
        """智能记忆管理"""
        if self.token_count > self.max_tokens * 0.8:  # 80% 阈值触发
            self._compress_history()
    
    def _compress_history(self) -> None:
        """
        压缩历史记录
        保留: system prompt + 记忆摘要 + 最近消息
        """
        if len(self.messages) <= self.recent_messages_count + 1:
            return
        
        # 提取 system prompt
        system_msg = None
        if self.messages and self.messages[0].role == "system":
            system_msg = self.messages[0]
        
        # 需要压缩的旧消息
        old_messages = self.messages[1:-self.recent_messages_count] if system_msg else self.messages[:-self.recent_messages_count]
        
        # 生成历史摘要
        if old_messages:
            summary_parts = []
            for msg in old_messages:
                if msg.role == "assistant":
                    # 保留玩家的关键发言
                    summary_parts.append(f"[我的发言] {msg.content[:50]}...")
                elif msg.role == "user" and "投票" in msg.content:
                    summary_parts.append("[进行了投票]")
                elif msg.role == "user" and "描述" in msg.content:
                    summary_parts.append("[进行了描述阶段]")
            
            if summary_parts:
                new_summary = "; ".join(summary_parts[-5:])  # 只保留最后5条摘要
                self.memory_summary = new_summary
        
        # 保留最近消息
        recent = self.messages[-self.recent_messages_count:]
        
        # 重建消息列表
        self.messages = []
        if system_msg:
            self.messages.append(system_msg)
        
        # 注入记忆摘要到第一条 user 消息前
        if self.memory_summary:
            self.messages.append(Message(
                role="user",
                content=f"[历史记忆摘要] {self.memory_summary}"
            ))
            self.messages.append(Message(
                role="assistant", 
                content="我已了解之前的情况，请继续。"
            ))
        
        self.messages.extend(recent)
        
        # 重新计算 token
        self.token_count = sum(len(m.content) // 3 for m in self.messages)
    
    def to_openai_format(self) -> list[dict]:
        """转换为 OpenAI API 格式"""
        return [{"role": m.role, "content": m.content} for m in self.messages]
    
    def clear(self) -> None:
        """清空对话历史"""
        self.messages = []
        self.token_count = 0
        self.memory_summary = ""
    
    def get_stats(self) -> dict:
        """获取记忆统计"""
        return {
            "player": self.player_name,
            "message_count": len(self.messages),
            "token_count": self.token_count,
            "max_tokens": self.max_tokens,
            "usage_percent": round(self.token_count / self.max_tokens * 100, 1),
            "has_summary": bool(self.memory_summary)
        }


class PlayerSession(BaseModel):
    """玩家会话"""
    player_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    role: Optional[Role] = None
    word: Optional[str] = None
    is_alive: bool = True
    llm_provider: str
    llm_model: str
    
    # 对话上下文
    conversation: Optional[ConversationContext] = None
    
    # 个性配置
    persona: Optional[dict] = None
    
    # 游戏中的行为记录
    descriptions: list[str] = Field(default_factory=list)
    votes: list[str] = Field(default_factory=list)
    
    def model_post_init(self, __context) -> None:
        if self.conversation is None:
            self.conversation = ConversationContext(player_name=self.name)
    
    class Config:
        use_enum_values = True


class RoundRecord(BaseModel):
    """轮次记录"""
    round_number: int
    phase: GamePhase = GamePhase.DESCRIPTION
    descriptions: dict[str, str] = Field(default_factory=dict)
    # "谁不是人类"投票
    human_votes: dict[str, str] = Field(default_factory=dict)
    human_vote_counts: dict[str, int] = Field(default_factory=dict)
    # 卧底投票
    votes: dict[str, str] = Field(default_factory=dict)
    vote_counts: dict[str, int] = Field(default_factory=dict)
    eliminated: Optional[str] = None
    eliminated_role: Optional[Role] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GameSession(BaseModel):
    """游戏会话"""
    session_id: str = Field(
        default_factory=lambda: f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    
    # 游戏配置
    total_players: int = 0
    spy_count: int = 1
    civilian_word: str = ""
    spy_word: str = ""
    
    # 玩家
    players: dict[str, PlayerSession] = Field(default_factory=dict)
    
    # 游戏状态
    phase: GamePhase = GamePhase.WAITING
    current_round: int = 0
    speaking_order: list[str] = Field(default_factory=list)
    
    # 历史记录
    round_history: list[RoundRecord] = Field(default_factory=list)
    
    # 结果
    winner: Optional[Role] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def get_alive_players(self) -> list[PlayerSession]:
        """获取存活玩家"""
        return [p for p in self.players.values() if p.is_alive]
    
    def get_alive_player_names(self) -> list[str]:
        """获取存活玩家名称"""
        return [p.name for p in self.get_alive_players()]
    
    def get_spies(self) -> list[PlayerSession]:
        """获取存活的卧底"""
        return [p for p in self.players.values() if p.role == Role.SPY and p.is_alive]
    
    def get_civilians(self) -> list[PlayerSession]:
        """获取存活的平民"""
        return [p for p in self.players.values() if p.role == Role.CIVILIAN and p.is_alive]

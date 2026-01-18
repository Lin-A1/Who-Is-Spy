"""
游戏会话管理器
"""
import random
from datetime import datetime
from typing import Optional
from loguru import logger

from .models import (
    GameSession, PlayerSession, RoundRecord,
    Role, GamePhase, ConversationContext
)
from players.profiles import get_random_persona


class GameSessionManager:
    """
    游戏会话管理器
    
    职责:
    1. 游戏会话生命周期管理（创建、运行、结束）
    2. 玩家会话管理（加入、状态更新、淘汰）
    3. 游戏状态转换（状态机）
    4. 历史记录维护
    5. 对话上下文协调
    """
    
    def __init__(self):
        self._session: Optional[GameSession] = None
        self._session_store: dict[str, GameSession] = {}
    
    # ==================== 会话生命周期 ====================
    
    def create_session(
        self,
        player_configs: list[dict],
        spy_count: int = 1
    ) -> GameSession:
        """
        创建新游戏会话
        
        Args:
            player_configs: 玩家配置列表
                [{"name": "GPT-4", "provider": "openai", "model": "gpt-4"}, ...]
            spy_count: 卧底数量
        
        Returns:
            创建的 GameSession
        """
        session = GameSession(
            total_players=len(player_configs),
            spy_count=spy_count
        )
        
        logger.info(f"创建游戏会话: {session.session_id}")
        logger.info(f"玩家数量: {len(player_configs)}, 卧底数量: {spy_count}")
        
        # 创建玩家会话
        for config in player_configs:
            player = PlayerSession(
                name=config["name"],
                llm_provider=config["provider"],
                llm_model=config["model"],
                persona=None  # 不再分配性格
            )
            
            session.players[player.name] = player
            logger.debug(f"添加玩家: {player.name} ({player.llm_provider}/{player.llm_model})")
        
        # 随机生成发言顺序
        session.speaking_order = list(session.players.keys())
        random.shuffle(session.speaking_order)
        logger.info(f"发言顺序: {' -> '.join(session.speaking_order)}")
        
        self._session = session
        self._session_store[session.session_id] = session
        
        return session
    
    def get_current_session(self) -> Optional[GameSession]:
        """获取当前会话"""
        return self._session
    
    def get_session_by_id(self, session_id: str) -> Optional[GameSession]:
        """根据 ID 获取会话"""
        return self._session_store.get(session_id)
    
    def end_session(self, winner: Role) -> GameSession:
        """
        结束游戏会话
        
        Args:
            winner: 获胜方
        
        Returns:
            最终的 GameSession
        """
        if self._session is None:
            raise RuntimeError("No active session")
        
        self._session.winner = winner
        self._session.phase = GamePhase.FINISHED
        self._session.ended_at = datetime.now()
        
        winner_name = "平民" if winner == Role.CIVILIAN else "卧底"
        logger.info(f"游戏结束! 获胜方: {winner_name}")
        logger.info(f"游戏时长: {self._session.ended_at - self._session.started_at}")
        
        return self._session
    
    # ==================== 游戏初始化 ====================
    
    def initialize_game(self, civilian_word: str, spy_word: str) -> None:
        """
        初始化游戏: 分配角色、发词
        
        Args:
            civilian_word: 平民词
            spy_word: 卧底词
        """
        if self._session is None:
            raise RuntimeError("No active session")
        
        self._session.civilian_word = civilian_word
        self._session.spy_word = spy_word
        self._session.started_at = datetime.now()
        
        logger.info(f"词对: 平民词[{civilian_word}] vs 卧底词[{spy_word}]")
        
        # 随机选择卧底
        player_names = list(self._session.players.keys())
        spy_names = random.sample(player_names, self._session.spy_count)
        
        logger.debug(f"卧底玩家: {spy_names}")
        
        # 分配角色和词语
        for name, player in self._session.players.items():
            if name in spy_names:
                player.role = Role.SPY
                player.word = spy_word
                logger.info(f"[角色分配] {name}: 卧底 - 词语[{spy_word}]")
            else:
                player.role = Role.CIVILIAN
                player.word = civilian_word
                logger.info(f"[角色分配] {name}: 平民 - 词语[{civilian_word}]")
            
            # 初始化对话上下文
            self._init_player_context(player)
        
        self._session.phase = GamePhase.INIT
    
    def _init_player_context(self, player: PlayerSession) -> None:
        """初始化玩家的对话上下文"""
        system_prompt = self._build_system_prompt(player)
        player.conversation.add_message("system", system_prompt)
        logger.debug(f"[{player.name}] 对话上下文已初始化")
    
    def _build_system_prompt(self, player: PlayerSession) -> str:
        """构建系统提示词"""
        role_name = "平民" if player.role == Role.CIVILIAN else "卧底"
        
        # 极简中文 System Prompt
        if player.role == Role.CIVILIAN:
            role_rule = "你的词和其他平民相同。找出卧底，投票淘汰他。"
        else:
            role_rule = "你是卧底！你的词可能和平民不同。请伪装，避免被发现。"
        
        return f"""你正在参与一场「谁是卧底」游戏。

【你的身份】
名字：{player.name}
角色：{role_name}
词语：【{player.word}】
{role_rule}

【规则】
1. 每轮用一句话描述你的词语，但不能直接说出词语本身。
2. 描述结束后投票，票数最多的人被淘汰。
3. 平民目标：找出卧底。卧底目标：活到最后。

【重要】
做自己，像个真人一样说话。不要像 AI 助手那样回答。
"""
    
    # ==================== 状态转换 ====================
    
    def transition_phase(self, new_phase: GamePhase) -> None:
        """状态转换"""
        if self._session is None:
            raise RuntimeError("No active session")
        
        valid_transitions = {
            GamePhase.WAITING: [GamePhase.INIT],
            GamePhase.INIT: [GamePhase.DESCRIPTION],
            GamePhase.DESCRIPTION: [GamePhase.VOTING],
            GamePhase.VOTING: [GamePhase.ELIMINATION],
            GamePhase.ELIMINATION: [GamePhase.DESCRIPTION, GamePhase.FINISHED],
        }
        
        current = self._session.phase
        if new_phase not in valid_transitions.get(current, []):
            raise ValueError(f"Invalid transition: {current} -> {new_phase}")
        
        logger.info(f"[状态转换] {current.value} -> {new_phase.value}")
        self._session.phase = new_phase
    
    def start_new_round(self) -> int:
        """开始新一轮"""
        if self._session is None:
            raise RuntimeError("No active session")
        
        self._session.current_round += 1
        self.transition_phase(GamePhase.DESCRIPTION)
        
        # 创建新的轮次记录
        record = RoundRecord(
            round_number=self._session.current_round,
            phase=GamePhase.DESCRIPTION
        )
        self._session.round_history.append(record)
        
        logger.info(f"========== 第 {self._session.current_round} 轮开始 ==========")
        
        return self._session.current_round
    
    # ==================== 玩家状态管理 ====================
    
    def eliminate_player(self, player_name: str) -> PlayerSession:
        """淘汰玩家"""
        if self._session is None:
            raise RuntimeError("No active session")
        
        player = self._session.players.get(player_name)
        if player is None:
            raise ValueError(f"Player not found: {player_name}")
        
        player.is_alive = False
        
        # 更新当前轮次记录
        if self._session.round_history:
            self._session.round_history[-1].eliminated = player_name
            self._session.round_history[-1].eliminated_role = player.role
        
        role_name = "卧底" if player.role == Role.SPY else "平民"
        logger.info(f"🔴 {player_name} 被淘汰! 身份: {role_name}")
        
        return player
    
    def get_alive_speaking_order(self) -> list[str]:
        """获取存活玩家的发言顺序"""
        if self._session is None:
            return []
        
        alive_names = self._session.get_alive_player_names()
        return [name for name in self._session.speaking_order if name in alive_names]
    
    # ==================== 记录管理 ====================
    
    def record_description(self, player_name: str, description: str) -> None:
        """记录玩家描述"""
        if self._session is None or not self._session.round_history:
            raise RuntimeError("No active round")
        
        current_round = self._session.round_history[-1]
        current_round.descriptions[player_name] = description
        
        # 更新玩家会话
        player = self._session.players[player_name]
        player.descriptions.append(description)
        
        logger.info(f"[描述] {player_name}: {description}")
    
    def record_vote(self, voter: str, target: str) -> None:
        """记录投票"""
        if self._session is None or not self._session.round_history:
            raise RuntimeError("No active round")
        
        current_round = self._session.round_history[-1]
        current_round.votes[voter] = target
        
        # 更新玩家会话
        player = self._session.players[voter]
        player.votes.append(target)
        
        logger.info(f"[投票] {voter} -> {target}")
    
    def tally_votes(self) -> str:
        """统计投票，返回被淘汰的玩家名"""
        if self._session is None or not self._session.round_history:
            raise RuntimeError("No active round")
        
        votes = self._session.round_history[-1].votes
        vote_counts: dict[str, int] = {}
        
        for target in votes.values():
            vote_counts[target] = vote_counts.get(target, 0) + 1
        
        # 保存票数统计
        self._session.round_history[-1].vote_counts = vote_counts
        
        logger.info(f"[票数统计] {vote_counts}")
        
        # 找出票数最高的玩家
        max_votes = max(vote_counts.values())
        candidates = [name for name, count in vote_counts.items() if count == max_votes]
        
        eliminated = random.choice(candidates)
        
        if len(candidates) > 1:
            logger.info(f"票数相同: {candidates}, 随机淘汰: {eliminated}")
        
        return eliminated
    
    def record_human_vote(self, voter: str, target: str) -> None:
        """记录"谁不是人类"投票"""
        if self._session is None or not self._session.round_history:
            raise RuntimeError("No active round")
        
        current_round = self._session.round_history[-1]
        current_round.human_votes[voter] = target
        
        logger.info(f"[人类识别投票] {voter} 认为 {target} 不是人类")
    
    def tally_human_votes(self) -> dict[str, int]:
        """统计"谁不是人类"投票，返回票数统计"""
        if self._session is None or not self._session.round_history:
            raise RuntimeError("No active round")
        
        votes = self._session.round_history[-1].human_votes
        vote_counts: dict[str, int] = {}
        
        for target in votes.values():
            vote_counts[target] = vote_counts.get(target, 0) + 1
        
        # 保存票数统计
        self._session.round_history[-1].human_vote_counts = vote_counts
        
        logger.info(f"[人类识别票数统计] {vote_counts}")
        
        # 找出被认为"最不像人类"的玩家
        if vote_counts:
            max_votes = max(vote_counts.values())
            most_robotic = [name for name, count in vote_counts.items() if count == max_votes]
            logger.info(f"🤖 被认为最不像人类的玩家: {most_robotic}")
        
        return vote_counts
    
    # ==================== 上下文管理 ====================
    
    def get_player_context(self, player_name: str) -> ConversationContext:
        """获取玩家的对话上下文"""
        if self._session is None:
            raise RuntimeError("No active session")
        
        player = self._session.players.get(player_name)
        if player is None:
            raise ValueError(f"Player not found: {player_name}")
        
        return player.conversation
    
    def add_to_player_context(self, player_name: str, role: str, content: str) -> None:
        """向玩家上下文添加消息"""
        context = self.get_player_context(player_name)
        context.add_message(role, content)
        logger.debug(f"[{player_name}] 上下文添加 {role} 消息: {content[:50]}...")
    
    def format_round_history(self) -> str:
        """格式化历史记录为文本"""
        if self._session is None:
            return "(暂无历史记录)"
        
        if not self._session.round_history:
            return "(这是第一轮)"
        
        lines = []
        for record in self._session.round_history[:-1]:  # 排除当前轮
            lines.append(f"\n=== 第 {record.round_number} 轮 ===")
            
            for name in self._session.speaking_order:
                if name in record.descriptions:
                    desc = record.descriptions[name]
                    lines.append(f"【{name}】: {desc}")
            
            if record.eliminated:
                role_name = "卧底" if record.eliminated_role == Role.SPY else "平民"
                lines.append(f"\n🔴 本轮淘汰: {record.eliminated} ({role_name})")
        
        return "\n".join(lines) if lines else "(这是第一轮)"
    
    def format_current_round_descriptions(self) -> str:
        """格式化当前轮的描述"""
        if self._session is None or not self._session.round_history:
            return ""
        
        current_round = self._session.round_history[-1]
        lines = []
        
        for name in self._session.speaking_order:
            if name in current_round.descriptions:
                desc = current_round.descriptions[name]
                lines.append(f"【{name}】: {desc}")
        
        return "\n".join(lines)
    
    # ==================== 胜负判定 ====================
    
    def check_win_condition(self) -> Optional[Role]:
        """
        检查胜负
        
        Returns:
            Role.CIVILIAN: 平民获胜
            Role.SPY: 卧底获胜
            None: 游戏继续
        """
        if self._session is None:
            return None
        
        alive_spies = len(self._session.get_spies())
        alive_civilians = len(self._session.get_civilians())
        
        logger.debug(f"存活情况: 平民 {alive_civilians} vs 卧底 {alive_spies}")
        
        if alive_spies == 0:
            logger.info("🎉 所有卧底被淘汰，平民获胜!")
            return Role.CIVILIAN
        
        if alive_spies >= alive_civilians:
            logger.info("🎉 卧底数量 >= 平民数量，卧底获胜!")
            return Role.SPY
        
        return None

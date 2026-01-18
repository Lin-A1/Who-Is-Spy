"""
游戏引擎 - 控制游戏流程
"""
import asyncio
import random
from typing import Optional, Any
from loguru import logger

from .models import Role, GamePhase, GameSession
from .session_manager import GameSessionManager


class GameEngine:
    """
    游戏引擎
    
    负责控制游戏的完整流程：
    1. 初始化游戏
    2. 运行描述轮（每人最多200字）
    3. 运行"谁不是人类"投票轮（平票跳过）
    4. 运行卧底投票轮（平票辩论后再投票）
    5. 淘汰玩家
    6. 判断胜负（无轮次限制，直到分出胜负）
    """
    
    def __init__(
        self,
        session_manager: GameSessionManager,
        players: dict,  # name -> LLMPlayer
        max_description_length: int = 200,
        display: Optional[Any] = None  # 支持 GameDisplay 实例
    ):
        self.session_manager = session_manager
        self.players = players
        self.max_description_length = max_description_length
        self.display = display
    
    async def run_game(self) -> GameSession:
        """
        运行完整游戏（无轮次限制）
        
        Returns:
            完成的 GameSession
        """
        session = self.session_manager.get_current_session()
        if session is None:
            raise RuntimeError("No active session")
        
        logger.info("=" * 60)
        logger.info("🎮 游戏开始!")
        logger.info("=" * 60)
        
        while True:
            round_number = self.session_manager.start_new_round()
            
            if self.display:
                self.display.show_round_start(round_number)
            
            # 描述阶段
            await self.run_description_round()
            
            # "谁不是人类"投票阶段（平票跳过）
            await self.run_human_detection_round()
            
            # 卧底投票阶段（平票辩论）
            self.session_manager.transition_phase(GamePhase.VOTING)
            eliminated = await self.run_voting_round()
            
            # 淘汰阶段
            self.session_manager.transition_phase(GamePhase.ELIMINATION)
            eliminated_role = self.session_manager.eliminate_player(eliminated)
            
            leave_msg = ""
            if eliminated:
                try:
                    # 淘汰玩家发表遗言
                    player = self.players[eliminated]
                    leave_msg = await player.leave_message()
                except Exception as e:
                    logger.error(f"发表遗言失败: {e}")
            
            if self.display:
                self.display.show_elimination(eliminated, eliminated_role, leave_msg)
            
            # 检查胜负
            winner = self.session_manager.check_win_condition()
            if winner is not None:
                return self.session_manager.end_session(winner)
            
            # 显示存活玩家
            alive_players = session.get_alive_player_names()
            logger.info(f"存活玩家: {', '.join(alive_players)}")
    
    async def run_description_round(self) -> None:
        """运行描述阶段（每人最多200字）"""
        session = self.session_manager.get_current_session()
        
        logger.info("-" * 40)
        logger.info(f"📝 描述阶段（每人最多{self.max_description_length}字）")
        logger.info("-" * 40)
        
        if self.display:
            self.display.show_phase("DESCRIPTION")
        
        # 获取历史记录
        history = self.session_manager.format_round_history()
        
        # 按顺序让每个存活玩家描述
        speaking_order = self.session_manager.get_alive_speaking_order()
        
        for player_name in speaking_order:
            if player_name not in self.players:
                logger.warning(f"玩家 {player_name} 的 LLM 实例未找到")
                continue
            
            player = self.players[player_name]
            
            try:
                if self.display:
                    self.display.show_thinking(player_name)
                
                # 获取描述（带字数限制和存活玩家信息）
                description = await player.describe(
                    round_number=session.current_round,
                    history=history,
                    max_length=self.max_description_length,
                    alive_players=speaking_order
                )
                
                # 记录描述
                self.session_manager.record_description(player_name, description)
                
                if self.display:
                    # 获取玩家角色，但仅用于内部逻辑，实际显示时应由 Display 控制是否泄露
                    # 这里为了兼容 display.show_description 的接口，需要传 is_spy
                    # 但在前端模式下，我们可以选择不传或让前端忽略
                    is_spy = (session.players[player_name].role == Role.SPY)
                    self.display.show_description(player_name, description, is_spy)
                
                # 更新历史（用于后续玩家参考）
                history = self.session_manager.format_round_history()
                current_descs = self.session_manager.format_current_round_descriptions()
                if current_descs:
                    history = history + f"\n\n=== 第 {session.current_round} 轮（进行中）===\n" + current_descs
                
            except Exception as e:
                logger.error(f"玩家 {player_name} 描述失败: {e}")
                default_desc = "这个东西很常见。"
                self.session_manager.record_description(player_name, default_desc)
                if self.display:
                     self.display.show_description(player_name, default_desc)

    async def run_human_detection_round(self) -> dict[str, int]:
        """
        运行"谁不是人类"投票阶段
        
        规则：平票直接跳过，不做任何处理
        
        Returns:
            票数统计
        """
        session = self.session_manager.get_current_session()
        
        logger.info("-" * 40)
        logger.info("🤖 特殊投票：谁不是人类？（平票跳过）")
        logger.info("-" * 40)
        
        if self.display:
            self.display.show_phase("HUMAN DETECTION", "🤖")
        
        # 获取当前轮描述
        round_descriptions = self.session_manager.format_current_round_descriptions()
        
        # 存活玩家列表
        candidates = session.get_alive_player_names()
        
        # 收集投票
        speaking_order = self.session_manager.get_alive_speaking_order()
        
        for player_name in speaking_order:
            if player_name not in self.players:
                continue
            
            if self.display:
                self.display.show_thinking(player_name)
            
            player = self.players[player_name]
            
            try:
                vote_target = await player.vote_human(
                    candidates=[c for c in candidates if c != player_name],
                    round_descriptions=round_descriptions
                )
                
                valid_candidates = [c for c in candidates if c != player_name]
                if vote_target in valid_candidates:
                    self.session_manager.record_human_vote(player_name, vote_target)
                else:
                    fallback_vote = random.choice(valid_candidates) if valid_candidates else None
                    if fallback_vote:
                        logger.warning(f"{player_name} 人类识别投票无效，改为投 {fallback_vote}")
                        self.session_manager.record_human_vote(player_name, fallback_vote)
                        
            except Exception as e:
                logger.error(f"玩家 {player_name} 人类识别投票异常: {e}")
                valid_candidates = [c for c in candidates if c != player_name]
                if valid_candidates:
                    fallback_vote = random.choice(valid_candidates)
                    self.session_manager.record_human_vote(player_name, fallback_vote)
        
        # 统计投票（平票跳过，不淘汰）
        vote_counts = self.session_manager.tally_human_votes()
        
        # 检查是否平票
        if vote_counts:
            max_votes = max(vote_counts.values())
            top_candidates = [name for name, count in vote_counts.items() if count == max_votes]
            
            if len(top_candidates) > 1:
                logger.info(f"🔄 人类识别投票平票 ({', '.join(top_candidates)})，跳过此环节")
        
        return vote_counts
    
    async def run_voting_round(self) -> str:
        """
        运行卧底投票阶段
        
        规则：平票时两人辩论，然后重新投票（只投这两人）
        
        Returns:
            被淘汰的玩家名
        """
        session = self.session_manager.get_current_session()
        
        logger.info("-" * 40)
        logger.info("🗳️ 卧底投票阶段")
        logger.info("-" * 40)
        
        if self.display:
            self.display.show_phase("VOTING", "🗳️")
        
        # 获取当前轮描述
        round_descriptions = self.session_manager.format_current_round_descriptions()
        
        # 存活玩家列表
        candidates = session.get_alive_player_names()
        
        # 第一轮投票
        vote_counts = await self._collect_votes(candidates, round_descriptions)
        
        if self.display:
            self.display.show_vote_result(vote_counts)
        
        # 检查是否平票
        max_votes = max(vote_counts.values())
        top_candidates = [name for name, count in vote_counts.items() if count == max_votes]
        
        if len(top_candidates) > 1:
            # 平票，进入辩论环节
            logger.info(f"⚖️ 平票！{', '.join(top_candidates)} 需要进行辩论")
            
            if self.display:
                self.display.show_phase("DEBATE", "💬")
            
            eliminated = await self._run_debate_and_revote(top_candidates, round_descriptions)
        else:
            eliminated = top_candidates[0]
        
        return eliminated
    
    async def _collect_votes(self, candidates: list[str], round_descriptions: str) -> dict[str, int]:
        """收集投票"""
        session = self.session_manager.get_current_session()
        speaking_order = self.session_manager.get_alive_speaking_order()
        
        # 并行收集投票
        tasks = []
        for player_name in speaking_order:
            if player_name not in self.players:
                continue
            
        # 收集投票（错峰请求，防止 429）
        async def vote_with_delay(player_name: str):
            if player_name not in self.players:
                return None # Or raise an error, depending on desired behavior
            
            player = self.players[player_name]
            
            if self.display:
                self.display.show_thinking(player_name)
            
            await asyncio.sleep(random.uniform(1.0, 5.0))  # 1-5秒随机延迟
            return await self._get_player_vote(player, player_name, candidates, round_descriptions)

        tasks = [vote_with_delay(name) for name in speaking_order]
        votes_raw = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 记录投票
        for i, player_name in enumerate(speaking_order):
            if i < len(votes_raw) and not isinstance(votes_raw[i], Exception):
                vote_target = votes_raw[i]
                if vote_target in candidates and vote_target != player_name:
                    self.session_manager.record_vote(player_name, vote_target)
                    
                    if self.display:
                        self.display.show_vote(player_name, vote_target)
                else:
                    valid_candidates = [c for c in candidates if c != player_name]
                    if valid_candidates:
                        fallback_vote = random.choice(valid_candidates)
                        logger.warning(f"{player_name} 无效投票，改为投 {fallback_vote}")
                        self.session_manager.record_vote(player_name, fallback_vote)
                        if self.display:
                            self.display.show_vote(player_name, fallback_vote)
            else:
                valid_candidates = [c for c in candidates if c != player_name]
                if valid_candidates:
                    fallback_vote = random.choice(valid_candidates)
                    logger.warning(f"{player_name} 投票失败，随机投 {fallback_vote}")
                    self.session_manager.record_vote(player_name, fallback_vote)
                    if self.display:
                        self.display.show_vote(player_name, fallback_vote)
        
        # 统计投票
        eliminated = self.session_manager.tally_votes()
        
        # 返回票数统计
        if session.round_history:
            return session.round_history[-1].vote_counts
        return {}
    
    async def _run_debate_and_revote(self, tie_candidates: list[str], round_descriptions: str) -> str:
        """
        平票辩论和重新投票
        
        Args:
            tie_candidates: 平票的候选人列表
            round_descriptions: 本轮描述
        
        Returns:
            最终被淘汰的玩家名
        """
        logger.info("-" * 40)
        logger.info("💬 平票辩论环节")
        logger.info("-" * 40)
        
        # 收集辩护发言
        debate_contents = []
        
        for candidate in tie_candidates:
            if candidate not in self.players:
                continue
            
            if self.display:
                self.display.show_thinking(candidate)
            
            player = self.players[candidate]
            opponent = [c for c in tie_candidates if c != candidate][0] if len(tie_candidates) == 2 else "其他候选人"
            
            try:
                debate = await player.debate(
                    opponent=opponent,
                    round_descriptions=round_descriptions,
                    max_length=self.max_description_length
                )
                debate_contents.append(f"【{candidate}】: {debate}")
                logger.info(f"[辩护] {candidate}: {debate}")
                
                if self.display:
                    # 复用 show_description 显示辩论
                    is_spy = (self.session_manager.get_current_session().players[candidate].role == Role.SPY)
                    self.display.show_description(candidate, f"[辩护] {debate}", is_spy)
                    
            except Exception as e:
                logger.error(f"玩家 {candidate} 辩护失败: {e}")
                debate_contents.append(f"【{candidate}】: (辩护失败)")
        
        all_debate_content = "\n\n".join(debate_contents)
        
        # 其他玩家重新投票（只在平票候选人中选择）
        logger.info("-" * 40)
        logger.info("🗳️ 辩论后重新投票")
        logger.info("-" * 40)
        
        if self.display:
            self.display.show_phase("RE-VOTE", "🗳️")
        
        session = self.session_manager.get_current_session()
        speaking_order = self.session_manager.get_alive_speaking_order()
        
        # 只有非候选人才能投票
        voters = [name for name in speaking_order if name not in tie_candidates]
        
        vote_counts = {c: 0 for c in tie_candidates}
        
        for voter_name in voters:
            if voter_name not in self.players:
                continue
            
            if self.display:
                self.display.show_thinking(voter_name)
            
            player = self.players[voter_name]
            
            try:
                vote_target = await player.vote_after_debate(
                    candidates=tie_candidates,
                    debate_content=all_debate_content
                )
                
                if vote_target in tie_candidates:
                    vote_counts[vote_target] = vote_counts.get(vote_target, 0) + 1
                    logger.info(f"[辩论后投票] {voter_name} -> {vote_target}")
                    
                    if self.display:
                        self.display.show_vote(voter_name, vote_target)
                else:
                    # 无效投票，随机选择
                    fallback = random.choice(tie_candidates)
                    vote_counts[fallback] = vote_counts.get(fallback, 0) + 1
                    logger.warning(f"{voter_name} 无效投票，改为投 {fallback}")
                    
                    if self.display:
                        self.display.show_vote(voter_name, fallback)
                    
            except Exception as e:
                logger.error(f"玩家 {voter_name} 辩论后投票失败: {e}")
                fallback = random.choice(tie_candidates)
                vote_counts[fallback] = vote_counts.get(fallback, 0) + 1
        
        logger.info(f"[辩论后票数] {vote_counts}")
        
        if self.display:
            self.display.show_vote_result(vote_counts)
        
        # 确定被淘汰者
        max_votes = max(vote_counts.values()) if vote_counts.values() else 0
        top_candidates = [name for name, count in vote_counts.items() if count == max_votes]
        
        if len(top_candidates) > 1:
            # 仍然平票，随机淘汰
            eliminated = random.choice(top_candidates)
            logger.info(f"辩论后仍平票，随机淘汰: {eliminated}")
        else:
            eliminated = top_candidates[0] if top_candidates else random.choice(tie_candidates)
        
        return eliminated
    
    async def _get_player_vote(
        self,
        player,
        player_name: str,
        candidates: list[str],
        round_descriptions: str
    ) -> str:
        """获取单个玩家的卧底投票"""
        try:
            vote_target = await player.vote(
                candidates=[c for c in candidates if c != player_name],
                round_descriptions=round_descriptions
            )
            return vote_target
        except Exception as e:
            logger.error(f"玩家 {player_name} 投票异常: {e}")
            raise

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
            
            # 双重投票阶段（合并 AI 投票和 卧底投票）
            self.session_manager.transition_phase(GamePhase.VOTING)
            elim_spy, elim_ai = await self.run_combined_voting_round()
            
            # 处理淘汰
            # 如果某人同时被双杀，只处理一次
            eliminations = []
            if elim_ai: eliminations.append((elim_ai, "🤖 图灵测试失败"))
            if elim_spy: eliminations.append((elim_spy, "🗳️ 公投出局"))
            
            if eliminations:
                self.session_manager.transition_phase(GamePhase.ELIMINATION)
            
            processed_names = set()
            
            for name, reason in eliminations:
                if name in processed_names: continue
                if not session.players[name].is_alive: continue # 已经被前一个逻辑淘汰
                
                # 淘汰处理
                eliminated_player = self.session_manager.eliminate_player(name)
                eliminated_role = eliminated_player.role  # 提取角色
                processed_names.add(name)
                
                leave_msg = ""
                try:
                    # 淘汰玩家发表遗言
                    player = self.players[name]
                    leave_msg = await player.leave_message()
                except Exception as e:
                    logger.error(f"发表遗言失败: {e}")
                
                if self.display:
                    # 将原因加到遗言前或者单独显示
                    full_msg = f"[{reason}] {leave_msg}"
                    self.display.show_elimination(name, eliminated_role, full_msg)
            
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
                    alive_players=speaking_order,
                    display=self.display  # 传入 Display 以显示思考过程
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

    async def run_combined_voting_round(self) -> tuple[Optional[str], Optional[str]]:
        """
        双重投票回合
        Returns:
            (eliminated_by_spy_vote, eliminated_by_ai_vote)
        """
        session = self.session_manager.get_current_session()
        logger.info("-" * 40)
        logger.info("🗳️ 双重投票阶段 (卧底 + AI)")
        logger.info("-" * 40)
        
        if self.display:
            self.display.show_phase("VOTE", "🗳️")
            
        round_descriptions = self.session_manager.format_current_round_descriptions()
        candidates = session.get_alive_player_names()
        speaking_order = self.session_manager.get_alive_speaking_order()
        
        # 1. 收集投票
        spy_votes = {} # voter -> target
        ai_votes = {}  # voter -> target
        
        async def ask_vote(player_name):
            if player_name not in self.players: return
            player = self.players[player_name]
            
            try:
                # 随机延迟防止并发过高
                await asyncio.sleep(random.uniform(0.1, 1.0))
                
                votes = await asyncio.wait_for(
                    player.vote_combined(
                        candidates=[c for c in candidates if c != player_name],
                        round_descriptions=round_descriptions,
                        display=self.display
                    ),
                    timeout=30.0  # 30秒超时
                )
                
                # 记录有效票
                v_spy = votes.get("vote_spy")
                v_ai = votes.get("vote_ai")
                
                if v_spy in candidates and v_spy != player_name:
                    spy_votes[player_name] = v_spy
                else: 
                    # 无效或投自己 -> 随机
                    remains = [c for c in candidates if c != player_name]
                    spy_votes[player_name] = random.choice(remains) if remains else None
                    
                if v_ai in candidates and v_ai != player_name:
                    ai_votes[player_name] = v_ai
                else:
                    remains = [c for c in candidates if c != player_name]
                    ai_votes[player_name] = random.choice(remains) if remains else None
                    
                # 显示
                if self.display:
                    # 显示两个投票太长，合并显示或者分行
                    # 这里简单显示Spy票，AI票隐式处理，最后显示结果
                    self.display.show_vote(player_name, str(v_spy))
                    
            except Exception as e:
                logger.error(f"{player_name} 投票失败: {e}")
                # 随机票
                remains = [c for c in candidates if c != player_name]
                if remains:
                    spy_votes[player_name] = random.choice(remains)
                    ai_votes[player_name] = random.choice(remains)

        tasks = [ask_vote(name) for name in speaking_order]
        await asyncio.gather(*tasks)
        
        # 2. 统计
        spy_counts = {}
        for target in spy_votes.values():
            if target: spy_counts[target] = spy_counts.get(target, 0) + 1
            
        ai_counts = {}
        for target in ai_votes.values():
            if target: ai_counts[target] = ai_counts.get(target, 0) + 1
            
        # 3. 显示结果
        if self.display:
            self.display.show_vote_result(spy_counts, title="🗳️ 卧底投票结果")
            self.display.show_vote_result(ai_counts, title="🤖 AI含量投票结果")
            
        # 4. 判定 AI 淘汰 (平票随机，或者不淘汰？策略：票数最高且超过1票才淘汰)
        elim_ai = None
        if ai_counts:
            max_ai = max(ai_counts.values())
            # 只有票数 > 1 才淘汰，防止乱杀
            if max_ai > 1:
                top_ai = [n for n, c in ai_counts.items() if c == max_ai]
                elim_ai = random.choice(top_ai) # 平票随机带走
        
        # 5. 判定 卧底淘汰 (平票需辩论)
        elim_spy = None
        if spy_counts:
            max_spy = max(spy_counts.values())
            top_spy = [n for n, c in spy_counts.items() if c == max_spy]
            
            if len(top_spy) > 1:
                # 平票辩论
                logger.info(f"⚖️ 卧底投票平票 {top_spy}，进入辩论")
                if self.display:
                    self.display.show_phase("DEBATE", "💬")
                
                elim_spy = await self._run_debate_and_revote(top_spy, round_descriptions)
            else:
                elim_spy = top_spy[0]
                
        # 记录到 Session (简化，只记录 Vote Counts)
        # self.session_manager.record_round_votes(...) # 现在的 API 比较复杂，暂时略过详细记录
        
        return elim_spy, elim_ai
    
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
                round_descriptions=round_descriptions,
                display=self.display
            )
            return vote_target
        except Exception as e:
            logger.error(f"玩家 {player_name} 投票异常: {e}")
            raise

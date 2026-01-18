"""
游戏日志系统 - 完整内容存储
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from loguru import logger

from core.models import GameSession, Role


class GameLogger:
    """
    游戏日志管理器
    
    功能：
    1. 控制台日志输出（彩色）
    2. 文件日志存储（完整详细日志）
    3. JSON 格式游戏记录导出
    4. Markdown 格式游戏报告生成
    """
    
    def __init__(
        self,
        log_dir: str = "logs",
        session_id: Optional[str] = None
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 生成会话 ID
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = session_id
        
        # 日志文件路径
        self.log_file = self.log_dir / f"{session_id}.log"
        self.json_file = self.log_dir / f"{session_id}.json"
        self.md_file = self.log_dir / f"{session_id}.md"
        
        # 配置 loguru
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """配置日志器"""
        # 移除默认处理器
        logger.remove()
        
        # 控制台输出（已禁用，由 GameDisplay 接管）
        # logger.add(
        #     sys.stdout,
        #     format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        #     level="INFO",
        #     colorize=True
        # )
        
        # 文件输出（详细格式，包含所有日志）
        logger.add(
            self.log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level="DEBUG",
            encoding="utf-8",
            rotation="10 MB"
        )
        
        logger.info(f"日志系统初始化完成")
        logger.info(f"日志文件: {self.log_file}")
    
    def save_session_json(self, session: GameSession) -> str:
        """
        保存游戏会话为 JSON 格式
        
        Args:
            session: 游戏会话对象
        
        Returns:
            JSON 文件路径
        """
        # 转换为可序列化的字典
        data = self._session_to_dict(session)
        
        with open(self.json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"游戏记录已保存: {self.json_file}")
        return str(self.json_file)
    
    def save_session_markdown(self, session: GameSession) -> str:
        """
        保存游戏报告为 Markdown 格式
        
        Args:
            session: 游戏会话对象
        
        Returns:
            Markdown 文件路径
        """
        md_content = self._generate_markdown_report(session)
        
        with open(self.md_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        logger.info(f"游戏报告已保存: {self.md_file}")
        return str(self.md_file)
    
    def _session_to_dict(self, session: GameSession) -> dict:
        """将 GameSession 转换为字典"""
        players_data = {}
        for name, player in session.players.items():
            players_data[name] = {
                "player_id": player.player_id,
                "name": player.name,
                "role": player.role.value if player.role else None,
                "word": player.word,
                "is_alive": player.is_alive,
                "llm_provider": player.llm_provider,
                "llm_model": player.llm_model,
                "descriptions": player.descriptions,
                "votes": player.votes,
                "conversation": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat()
                    }
                    for msg in player.conversation.messages
                ] if player.conversation else []
            }
        
        rounds_data = []
        for record in session.round_history:
            rounds_data.append({
                "round_number": record.round_number,
                "descriptions": record.descriptions,
                "human_votes": record.human_votes,
                "human_vote_counts": record.human_vote_counts,
                "votes": record.votes,
                "vote_counts": record.vote_counts,
                "eliminated": record.eliminated,
                "eliminated_role": record.eliminated_role.value if record.eliminated_role else None,
                "timestamp": record.timestamp.isoformat()
            })
        
        return {
            "session_id": session.session_id,
            "total_players": session.total_players,
            "spy_count": session.spy_count,
            "civilian_word": session.civilian_word,
            "spy_word": session.spy_word,
            "players": players_data,
            "speaking_order": session.speaking_order,
            "round_history": rounds_data,
            "winner": session.winner.value if session.winner else None,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None
        }
    
    def _generate_markdown_report(self, session: GameSession) -> str:
        """生成 Markdown 格式的游戏报告"""
        lines = []
        
        # 标题
        lines.append(f"# 🎮 谁是卧底游戏记录")
        lines.append(f"")
        lines.append(f"**会话 ID**: `{session.session_id}`")
        lines.append(f"**开始时间**: {session.started_at}")
        lines.append(f"**结束时间**: {session.ended_at}")
        
        if session.started_at and session.ended_at:
            duration = session.ended_at - session.started_at
            lines.append(f"**游戏时长**: {duration}")
        
        lines.append(f"")
        
        # 词对
        lines.append(f"## 📝 词对信息")
        lines.append(f"")
        lines.append(f"| 类型 | 词语 |")
        lines.append(f"|------|------|")
        lines.append(f"| 平民词 | **{session.civilian_word}** |")
        lines.append(f"| 卧底词 | **{session.spy_word}** |")
        lines.append(f"")
        
        # 玩家信息
        lines.append(f"## 👥 玩家信息")
        lines.append(f"")
        lines.append(f"| 玩家 | 身份 | LLM | 最终状态 |")
        lines.append(f"|------|------|-----|----------|")
        
        for name in session.speaking_order:
            player = session.players[name]
            role_emoji = "🕵️" if player.role == Role.SPY else "👤"
            role_name = "卧底" if player.role == Role.SPY else "平民"
            status = "✅ 存活" if player.is_alive else "❌ 淘汰"
            llm_info = f"{player.llm_provider}/{player.llm_model}"
            lines.append(f"| {role_emoji} {name} | {role_name} | `{llm_info}` | {status} |")
        
        lines.append(f"")
        
        # 游戏过程
        lines.append(f"## 🎲 游戏过程")
        lines.append(f"")
        
        for record in session.round_history:
            lines.append(f"### 第 {record.round_number} 轮")
            lines.append(f"")
            
            # 描述阶段
            lines.append(f"#### 📢 描述阶段")
            lines.append(f"")
            
            for name in session.speaking_order:
                if name in record.descriptions:
                    player = session.players[name]
                    role_emoji = "🕵️" if player.role == Role.SPY else "👤"
                    desc = record.descriptions[name]
                    lines.append(f"- {role_emoji} **{name}**: {desc}")
            
            lines.append(f"")
            
            # "谁不是人类"投票
            if record.human_votes:
                lines.append(f"#### 🤖 谁不是人类？")
                lines.append(f"")
                
                for voter, target in record.human_votes.items():
                    lines.append(f"- {voter} 认为 {target} 不是人类")
                
                lines.append(f"")
                
                if record.human_vote_counts:
                    lines.append(f"**统计**: ")
                    vote_str = ", ".join([f"{name}: {count}票" for name, count in record.human_vote_counts.items()])
                    lines.append(f"{vote_str}")
                    lines.append(f"")
            
            # 卧底投票阶段
            lines.append(f"#### 🗳️ 卧底投票")
            lines.append(f"")
            
            for voter, target in record.votes.items():
                lines.append(f"- {voter} → {target}")
            
            lines.append(f"")
            
            # 票数统计
            if record.vote_counts:
                lines.append(f"**票数统计**: ")
                vote_str = ", ".join([f"{name}: {count}票" for name, count in record.vote_counts.items()])
                lines.append(f"{vote_str}")
                lines.append(f"")
            
            # 淘汰结果
            if record.eliminated:
                role_name = "卧底" if record.eliminated_role == Role.SPY else "平民"
                lines.append(f"🔴 **本轮淘汰**: {record.eliminated} ({role_name})")
                lines.append(f"")
            
            lines.append(f"---")
            lines.append(f"")
        
        # 游戏结果
        lines.append(f"## 🏆 游戏结果")
        lines.append(f"")
        
        if session.winner == Role.CIVILIAN:
            lines.append(f"### 🎉 平民获胜！")
            lines.append(f"")
            lines.append(f"所有卧底已被成功识别并淘汰。")
        else:
            lines.append(f"### 🎉 卧底获胜！")
            lines.append(f"")
            lines.append(f"卧底成功隐藏身份存活到最后。")
        
        lines.append(f"")
        
        # 玩家对话记录
        lines.append(f"## 💬 详细对话记录")
        lines.append(f"")
        
        for name in session.speaking_order:
            player = session.players[name]
            role_name = "卧底" if player.role == Role.SPY else "平民"
            
            lines.append(f"### {name} ({role_name})")
            lines.append(f"")
            lines.append(f"<details>")
            lines.append(f"<summary>展开查看完整对话</summary>")
            lines.append(f"")
            lines.append(f"```")
            
            if player.conversation:
                for msg in player.conversation.messages:
                    lines.append(f"[{msg.role}]")
                    lines.append(f"{msg.content}")
                    lines.append(f"")
            
            lines.append(f"```")
            lines.append(f"</details>")
            lines.append(f"")
        
        return "\n".join(lines)
    
    def log_game_start(self, session: GameSession) -> None:
        """记录游戏开始"""
        logger.info("=" * 60)
        logger.info("🎮 谁是卧底 - 游戏开始")
        logger.info("=" * 60)
        logger.info(f"会话 ID: {session.session_id}")
        logger.info(f"玩家数量: {session.total_players}")
        logger.info(f"卧底数量: {session.spy_count}")
        logger.info(f"词对: {session.civilian_word} vs {session.spy_word}")
        logger.info(f"发言顺序: {' -> '.join(session.speaking_order)}")
        logger.info("=" * 60)
    
    def log_game_end(self, session: GameSession) -> None:
        """记录游戏结束"""
        logger.info("=" * 60)
        
        if session.winner == Role.CIVILIAN:
            logger.info("🎉 游戏结束 - 平民获胜!")
        else:
            logger.info("🎉 游戏结束 - 卧底获胜!")
        
        logger.info(f"总轮数: {session.current_round}")
        
        if session.started_at and session.ended_at:
            duration = session.ended_at - session.started_at
            logger.info(f"游戏时长: {duration}")
        
        logger.info("=" * 60)
        
        # 保存记录
        self.save_session_json(session)
        self.save_session_markdown(session)

import asyncio
import json
from .display import GameDisplay
from core.models import GameSession, Role

class WebGameDisplay(GameDisplay):
    """
    Web 适配显示器
    同时输出到终端(Rich)和 WebSocket
    """
    
    def __init__(self, broadcast_queue: asyncio.Queue):
        super().__init__()
        self.queue = broadcast_queue
    
    def _send(self, event_type: str, payload: dict):
        """发送事件到队列"""
        message = {
            "type": event_type,
            "payload": payload
        }
        # 使用 put_nowait 非阻塞放入队列
        try:
            self.queue.put_nowait(json.dumps(message))
        except Exception:
            pass

    def show_players(self, session: GameSession, reveal_roles: bool = False) -> None:
        super().show_players(session, reveal_roles)
        
        # 构建玩家列表数据
        players_data = []
        for name, player in session.players.items():
            p_data = {
                "name": name,
                "model": f"{player.llm_provider}/{player.llm_model}",
                "is_alive": player.is_alive,
                "role": player.role if reveal_roles else None
            }
            players_data.append(p_data)
        
        # 这种事件通常意味着游戏初始化或状态刷新
        # 这里我们假设它是 game_start 的一部分信息，或者专门的 update
        # 暂时只在 game_start 发送完整列表，这里仅作终端显示
        pass

    def show_round_start(self, round_number: int) -> None:
        super().show_round_start(round_number)
        self._send("round_start", {"round_number": round_number})

    def show_phase(self, phase_name: str, emoji: str = "📝") -> None:
        super().show_phase(phase_name, emoji)
        self._send("phase_change", {"phase": phase_name})

    def show_thinking(self, player_name: str) -> None:
        super().show_thinking(player_name)
        self._send("player_speaking", {"player_name": player_name})

    def show_description(self, player_name: str, description: str, is_spy: bool = False) -> None:
        super().show_description(player_name, description, is_spy)
        self._send("description", {
            "player_name": player_name, 
            "content": description,
            "is_spy": is_spy
        })

    def show_vote(self, voter: str, target: str) -> None:
        super().show_vote(voter, target)
        self._send("vote", {"voter": voter, "target": target})

    def show_vote_result(self, vote_counts: dict[str, int]) -> None:
        super().show_vote_result(vote_counts)
        self._send("vote_result", {"counts": vote_counts})

    def show_elimination(self, player_name: str, role: Role, leave_message: str = "") -> None:
        super().show_elimination(player_name, role)
        
        # 终端显示遗言
        if leave_message:
            # 简单打印，不引入 rich 依赖防止报错，super() 里已经有 rich table 了
            pass 
            
        self._send("elimination", {
            "player_name": player_name, 
            "role": role,
            "leave_message": leave_message
        })

    def show_game_result(self, session: GameSession) -> None:
        super().show_game_result(session)
        self._send("game_end", {"winner": session.winner})
    
    def show_error(self, message: str) -> None:
        super().show_error(message)
        self._send("error", {"message": message})
        
    def send_game_init(self, session: GameSession, civilian_word: str, spy_word: str):
        """发送游戏初始化数据 (Web 特有)"""
        players_data = []
        # 按发言顺序排序
        for name in session.speaking_order:
            p = session.players[name]
            players_data.append({
                "name": name,
                "model": f"{p.llm_provider}/{p.llm_model}",
                "role": p.role
            })
            
        self._send("game_start", {
            "players": players_data,
            "civilian_word": civilian_word,
            "spy_word": spy_word
        })

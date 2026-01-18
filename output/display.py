"""
游戏展示模块 - 终端 UI
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import box

from core.models import GameSession, Role


console = Console()


class GameDisplay:
    """
    游戏展示器
    
    使用 rich 库提供美观的终端界面
    """
    
    def __init__(self):
        self.console = Console()
    
    def show_welcome(self) -> None:
        """显示欢迎界面"""
        title = Text()
        title.append("🎮 ", style="bold")
        title.append("谁是卧底", style="bold magenta")
        title.append(" 🎮", style="bold")
        
        welcome_panel = Panel(
            "[bold cyan]欢迎来到 LLM 版本的谁是卧底游戏![/bold cyan]\n\n"
            "[dim]在这个游戏中，多个 AI 将互相对抗，\n"
            "尝试找出隐藏其中的卧底！[/dim]",
            title=title,
            border_style="magenta",
            padding=(1, 2)
        )
        
        self.console.print(welcome_panel)
        self.console.print()
    
    def show_players(self, session: GameSession, reveal_roles: bool = False) -> None:
        """
        显示玩家列表
        
        Args:
            session: 游戏会话
            reveal_roles: 是否显示角色（游戏结束后设为 True）
        """
        table = Table(
            title="👥 玩家列表",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        
        table.add_column("玩家", style="bold")
        table.add_column("LLM", style="dim")
        
        if reveal_roles:
            table.add_column("身份", style="bold")
            table.add_column("词语")
        
        table.add_column("状态")
        
        for name in session.speaking_order:
            player = session.players[name]
            
            llm_info = f"{player.llm_provider}/{player.llm_model}"
            status = "[green]✅ 存活[/green]" if player.is_alive else "[red]❌ 淘汰[/red]"
            
            if reveal_roles:
                if player.role == Role.SPY:
                    role_str = "[red]🕵️ 卧底[/red]"
                else:
                    role_str = "[blue]👤 平民[/blue]"
                
                table.add_row(name, llm_info, role_str, player.word, status)
            else:
                table.add_row(name, llm_info, status)
        
        self.console.print(table)
        self.console.print()
    
    def show_round_start(self, round_number: int) -> None:
        """显示轮次开始"""
        self.console.rule(f"[bold yellow]第 {round_number} 轮[/bold yellow]", style="yellow")
        self.console.print()
    
    def show_phase(self, phase_name: str, emoji: str = "📝") -> None:
        """显示阶段"""
        self.console.print(f"\n{emoji} [bold cyan]{phase_name}[/bold cyan]")
        self.console.print("-" * 40)
    
    def show_description(self, player_name: str, description: str, is_spy: bool = False) -> None:
        """显示玩家描述"""
        border_style = "red" if is_spy else "cyan"
        title = f"[bold {border_style}]{player_name}[/bold {border_style}]"
        
        self.console.print(Panel(
            description,
            title=title,
            border_style=border_style,
            expand=False,
            padding=(0, 2)
        ))
    
    def show_vote(self, voter: str, target: str) -> None:
        """显示投票"""
        self.console.print(f"  🗳️ {voter} [dim]→[/dim] [bold]{target}[/bold]")
    
    def show_vote_result(self, vote_counts: dict[str, int], title: str = "📊 票数统计") -> None:
        """显示投票结果"""
        self.console.print()
        
        table = Table(title=title, box=box.SIMPLE)
        table.add_column("玩家", style="bold")
        table.add_column("票数", style="cyan")
        
        # 按票数排序
        sorted_votes = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)
        
        for name, count in sorted_votes:
            bars = "█" * count
            table.add_row(name, f"{count} {bars}")
        
        self.console.print(table)
    
    def show_elimination(self, player_name: str, role: Role, leave_message: str = "") -> None:
        """显示淘汰结果"""
        role_name = "卧底" if role == Role.SPY else "平民"
        role_emoji = "🕵️" if role == Role.SPY else "👤"
        
        content = f"[bold]{player_name}[/bold] 被淘汰!\n身份: {role_emoji} [bold]{role_name}[/bold]"
        if leave_message:
            content += f"\n\n[italic]遗言: {leave_message}[/italic]"
            
        self.console.print()
        
        panel = Panel(
            content,
            title="🔴 淘汰",
            border_style="red"
        )
        
        self.console.print(panel)
        self.console.print()
        
    def show_game_result(self, session: GameSession) -> None:
        """显示游戏结果"""
        self.console.print()
        self.console.rule("[bold]游戏结束[/bold]", style="magenta")
        self.console.print()
        
        if session.winner == Role.CIVILIAN:
            winner_text = "[bold green]🎉 平民获胜! 🎉[/bold green]"
            desc = "所有卧底已被成功识别并淘汰！"
        else:
            winner_text = "[bold red]🎉 卧底获胜! 🎉[/bold red]"
            desc = "卧底成功隐藏身份存活到最后！"
        
        panel = Panel(
            f"{winner_text}\n\n{desc}\n\n"
            f"[dim]词对: {session.civilian_word} vs {session.spy_word}[/dim]\n"
            f"[dim]总轮数: {session.current_round}[/dim]",
            title="🏆 游戏结果",
            border_style="magenta",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
        
        # 显示最终玩家状态
        self.show_players(session, reveal_roles=True)
        
    def show_thinking(self, player_name: str) -> None:
        """显示正在思考的状态"""
        self.console.print(f"  [dim]⏳ {player_name} 正在思考...[/dim]")

    def show_thought(self, player_name: str, content: str) -> None:
        """显示具体的思考内容"""
        self.console.print(f"  [dim]💭 {player_name} 思考: {content.strip()}[/dim]")

    def clear_thinking(self) -> None:
        """清除思考提示"""
        self.console.print(" " * 50, end="\r")
    
    def show_error(self, message: str) -> None:
        """显示错误"""
        self.console.print(f"[bold red]❌ 错误:[/bold red] {message}")
    
    def show_info(self, message: str) -> None:
        """显示信息"""
        self.console.print(f"[bold blue]ℹ️[/bold blue] {message}")

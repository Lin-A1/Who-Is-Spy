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
        
    def show_thinking(self, player_name: str) -> None:
        pass # 不再需要简单的 loading，因为有详细 thought

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

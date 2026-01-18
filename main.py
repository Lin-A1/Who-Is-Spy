#!/usr/bin/env python3
"""
谁是卧底 - LLM 版本
主入口文件

支持的 LLM 玩家：
- Qwen (通义千问)
- Mimo (小米)
- Deepseek
- GLM (智谱)
- Kimi (月之暗面)
- MiniMax
- Ernie (文心一言)
"""
import asyncio
import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import config
from core.models import Role
from core.session_manager import GameSessionManager
from core.game_engine import GameEngine
from players.llm_client import LLMClient
from players.llm_player import LLMPlayer
from data.word_manager import WordManager
from output.logger import GameLogger
from output.display import GameDisplay


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="谁是卧底 - LLM 版本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                    # 使用所有可用的 LLM（默认 1 名卧底）
  python main.py --spies 2          # 2 名卧底
  python main.py --max-length 100   # 每轮描述最多 100 字
  python main.py --skip-check       # 跳过 LLM 连通性检查
        """
    )
    
    parser.add_argument(
        "--spies", "-s",
        type=int,
        default=None,
        help="卧底数量（默认从 .env 读取或使用 1）"
    )
    
    parser.add_argument(
        "--max-length", "-m",
        type=int,
        default=None,
        help="每轮描述最大字数（默认 200）"
    )
    
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="跳过 LLM 连通性检查"
    )

    parser.add_argument(
        "--civilian-word",
        type=str,
        help="自定义平民词"
    )

    parser.add_argument(
        "--spy-word",
        type=str,
        help="自定义卧底词"
    )
    
    return parser.parse_args()


async def check_all_llm_connections(
    player_configs: list[dict],
    display: GameDisplay
) -> tuple[bool, dict[str, LLMClient]]:
    """
    检查所有 LLM 是否可以连通
    
    Args:
        player_configs: 玩家配置列表
        display: 显示对象
    
    Returns:
        (all_passed, clients_dict) - 是否全部通过，以及客户端字典
    """
    display.show_info("")
    display.show_info("=" * 50)
    display.show_info("🔍 正在检查 LLM 连通性...")
    display.show_info("=" * 50)
    
    clients = {}
    all_passed = True
    failed_providers = []
    
    # 创建所有客户端
    for pc in player_configs:
        provider_name = pc["provider"]
        provider_config = config.get_provider(provider_name)
        
        client = LLMClient(
            api_key=provider_config.api_key,
            base_url=provider_config.base_url,
            model=provider_config.model,
            temperature=provider_config.temperature
        )
        
        clients[pc["name"]] = client
    
    # 并行检查所有连接
    tasks = []
    names = []
    for name, client in clients.items():
        tasks.append(client.health_check())
        names.append(name)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 显示结果
    for i, (name, result) in enumerate(zip(names, results)):
        if isinstance(result, Exception):
            display.show_error(f"  {name}: ❌ 连接失败 - {str(result)[:40]}")
            all_passed = False
            failed_providers.append(name)
        else:
            success, message = result
            if success:
                display.show_info(f"  {message}")
            else:
                display.show_error(f"  {message}")
                all_passed = False
                failed_providers.append(name)
    
    display.show_info("")
    
    if all_passed:
        display.show_info("=" * 50)
        display.show_info("✅ 全部 LLM 连通性检查通过！")
        display.show_info("🎮 准备完毕，即将开始游戏...")
        display.show_info("=" * 50)
        display.show_info("")
    else:
        display.show_error("=" * 50)
        display.show_error(f"❌ 以下 LLM 连接失败: {', '.join(failed_providers)}")
        display.show_error("请检查 API Key 和网络连接后重试")
        display.show_error("或使用 --skip-check 跳过检查")
        display.show_error("=" * 50)
    
    return all_passed, clients


async def main():
    """主函数"""
    args = parse_args()
    display = GameDisplay()
    
    # 显示欢迎界面
    display.show_welcome()
    
    # 检查可用的 LLM 提供商
    available_providers = config.list_providers()
    
    if not available_providers:
        display.show_error("未找到可用的 LLM 提供商！")
        display.show_info("请在 .env 文件中配置 API Key")
        display.show_info("参考 .env.example 文件")
        return
    
    display.show_info(f"可用的 LLM 提供商: {', '.join(available_providers)}")
    
    # 确定配置
    spy_count = args.spies if args.spies else config.game.spy_count
    max_description_length = args.max_length if args.max_length else config.game.max_description_length
    
    # 验证参数
    player_count = len(available_providers)
    
    if player_count < 3:
        display.show_error("至少需要 3 个 LLM 提供商！")
        return
    
    if spy_count >= player_count:
        display.show_error("卧底数量必须小于玩家总数！")
        return
    
    # 使用 LLM 提供商名称作为玩家名称
    player_configs = []
    
    for provider_name in available_providers:
        provider_config = config.get_provider(provider_name)
        
        player_configs.append({
            "name": provider_name.upper(),  # 使用大写的提供商名作为玩家名
            "provider": provider_name,
            "model": provider_config.model
        })
    
    display.show_info(f"玩家配置: {player_count} 名玩家, {spy_count} 名卧底")
    display.show_info(f"每轮描述最多 {max_description_length} 字")
    display.show_info("")
    
    for pc in player_configs:
        display.show_info(f"  - {pc['name']}: {pc['model']}")
    
    # ========== 连通性检查 ==========
    if not args.skip_check:
        all_passed, llm_clients = await check_all_llm_connections(player_configs, display)
        
        if not all_passed:
            display.show_error("游戏无法开始，请修复连接问题后重试。")
            return
    else:
        display.show_info("")
        display.show_info("⚠️ 跳过 LLM 连通性检查")
        llm_clients = None
    
    # 初始化日志系统
    game_logger = GameLogger()
    
    # 初始化词库
    word_manager = WordManager()
    
    if args.civilian_word and args.spy_word:
        civilian_word = args.civilian_word
        spy_word = args.spy_word
        display.show_info(f"使用自定义词语: 平民[{civilian_word}] vs 卧底[{spy_word}]")
    else:
        civilian_word, spy_word = word_manager.get_random_pair()
    
    # 初始化会话管理器
    session_manager = GameSessionManager()
    session = session_manager.create_session(
        player_configs=player_configs,
        spy_count=spy_count
    )
    
    # 初始化游戏（分配角色、发词）
    session_manager.initialize_game(civilian_word, spy_word)
    
    # 创建 LLM 玩家（使用已检查过的客户端或新建）
    llm_players = {}
    
    for player_name, player_session in session.players.items():
        if llm_clients and player_name in llm_clients:
            # 使用已检查过的客户端
            client = llm_clients[player_name]
        else:
            # 新建客户端
            provider_config = config.get_provider(player_session.llm_provider)
            client = LLMClient(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=provider_config.model,
                temperature=provider_config.temperature
            )
        
        # 创建 LLM 玩家
        llm_player = LLMPlayer(
            name=player_name,
            client=client,
            session=player_session
        )
        
        llm_players[player_name] = llm_player
    
    # 记录游戏开始
    game_logger.log_game_start(session)
    
    # 显示玩家列表（不显示角色）
    display.show_players(session, reveal_roles=False)
    
    # 创建游戏引擎并运行游戏
    engine = GameEngine(
        session_manager=session_manager,
        players=llm_players,
        max_description_length=max_description_length
    )
    
    try:
        # 运行游戏
        final_session = await engine.run_game()
        
        # 显示游戏结果
        display.show_game_result(final_session)
        
        # 记录游戏结束
        game_logger.log_game_end(final_session)
        
    except KeyboardInterrupt:
        display.show_info("\n游戏被中断")
    except Exception as e:
        display.show_error(f"游戏异常: {e}")
        import traceback
        traceback.print_exc()
        raise


def run():
    """入口函数"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n游戏结束")


if __name__ == "__main__":
    run()

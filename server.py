import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uvicorn

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import config
from core.session_manager import GameSessionManager
from core.game_engine import GameEngine
from players.llm_client import LLMClient
from players.llm_player import LLMPlayer
from data.word_manager import WordManager
from output.logger import GameLogger
from output.web_adapter import WebGameDisplay

# 全局变量
broadcast_queue = asyncio.Queue()
game_background_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    asyncio.create_task(message_broadcaster())
    yield
    # Shutdown logic if needed

app = FastAPI(lifespan=lifespan)

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

# 挂载静态文件
app.mount("/static", StaticFiles(directory="web/static"), name="static")

@app.get("/")
async def get():
    return FileResponse('web/index.html')

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 保持连接，如果需要接收前端指令可以在这里处理
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def message_broadcaster():
    """从队列读取消息并广播"""
    while True:
        message = await broadcast_queue.get()
        await manager.broadcast(message)
        broadcast_queue.task_done()





class StartGameRequest(BaseModel):
    civilian_word: Optional[str] = None
    spy_word: Optional[str] = None

@app.post("/start")
async def start_game(req: StartGameRequest):
    global game_background_task
    game_background_task = asyncio.create_task(
        run_game_logic(req.civilian_word, req.spy_word)
    )
    return {"status": "started"}

async def run_game_logic(custom_civilian_word: str = None, custom_spy_word: str = None):
    """运行游戏逻辑"""
    try:
        # 重置配置
        logger.info("Server: Initializing game...")
        
        # 1. 初始化显示适配器
        display = WebGameDisplay(broadcast_queue)
        
        # 2. 检查可用 LLM
        available_providers = config.list_providers()
        
        player_configs = []
        for provider_name in available_providers:
            provider_config = config.get_provider(provider_name)
            player_configs.append({
                "name": provider_name.upper(),
                "provider": provider_name,
                "model": provider_config.model
            })

        if len(player_configs) < 3:
            display.show_error("Not enough players configured!")
            return

        # 3. 初始化游戏组件
        game_logger = GameLogger()
        word_manager = WordManager()
        
        if custom_civilian_word and custom_spy_word:
            civilian_word = custom_civilian_word
            spy_word = custom_spy_word
            display.show_info(f"Using Custom Words: {civilian_word} vs {spy_word}")
        else:
            civilian_word, spy_word = word_manager.get_random_pair()
            
        session_manager = GameSessionManager()
        
        session = session_manager.create_session(
            player_configs=player_configs,
            spy_count=config.game.spy_count
        )
        
        session_manager.initialize_game(civilian_word, spy_word)
        
        # 4. 发送初始化事件给前端
        display.send_game_init(session, civilian_word, spy_word)
        
        # 5. 创建玩家
        llm_players = {}
        for player_name, player_session in session.players.items():
            provider_config = config.get_provider(player_session.llm_provider)
            
            client = LLMClient(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=provider_config.model,
                temperature=provider_config.temperature
            )
            
            llm_player = LLMPlayer(
                name=player_name,
                client=client,
                session=player_session
            )
            llm_players[player_name] = llm_player
        
        game_logger.log_game_start(session)
        display.show_players(session)
        
        # 6. 运行引擎
        # 修改 GameEngine 的 run_game 方法，使其可以使用新的 display
        # 但 GameEngine 并不直接依赖 display，它通过 session_manager 和 logger
        # 等等，之前的代码里 GameDisplay 是用来在 main.py 里打印的，GameEngine 内部只用了 logger
        # 这是一个问题：GameEngine 的内部状态变化并没有回调给 display！
        
        # 回顾 GameEngine 代码：它可以被直接修改，或者我们在这里通过轮询/hook的方式？
        # 不，最好的方式是把 display 传递给 GameEngine 并在关键节点调用。
        # 或者，我们只能 Hack GameEngine。
        
        # 让我们检查 GameEngine。
        
        # 临时方案：我们直接在这里创建一个特殊的 GameEngine 版本，或者修改现有的 GameEngine 增加回调支持
        # 为了快速实现，我将修改 GameEngine，增加一个 display 参数 (Optional)
        
        engine = GameEngine(
            session_manager=session_manager,
            players=llm_players,
            max_description_length=config.game.max_description_length
        )
        # 为 engine 注入 display (需要修改 GameEngine 类 或 Monkey Patch)
        engine.display = display 
        
        # 运行
        final_session = await engine.run_game()
        
        display.show_game_result(final_session)
        game_logger.log_game_end(final_session)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        if 'display' in locals():
            display.show_error(str(e))



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

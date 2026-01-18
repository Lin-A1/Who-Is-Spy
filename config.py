"""
配置管理模块
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMProviderConfig:
    """LLM 提供商配置"""
    name: str
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 500


@dataclass
class GameConfig:
    """游戏配置"""
    spy_count: int = 2
    player_count: int = 7  # 玩家数量
    max_description_length: int = 200  # 每轮描述最大字数
    description_timeout: float = 60.0  # 描述超时（秒）
    vote_timeout: float = 30.0  # 投票超时（秒）


@dataclass
class LogConfig:
    """日志配置"""
    log_dir: str = "logs"
    log_level: str = "DEBUG"
    save_json: bool = True
    save_markdown: bool = True


@dataclass
class Config:
    """全局配置"""
    game: GameConfig = field(default_factory=GameConfig)
    log: LogConfig = field(default_factory=LogConfig)
    providers: dict[str, LLMProviderConfig] = field(default_factory=dict)
    
    def __post_init__(self):
        # 从环境变量加载配置
        self.game.spy_count = int(os.getenv("GAME_SPY_COUNT", "2"))
        self.game.player_count = int(os.getenv("GAME_PLAYER_COUNT", "7"))
        self.game.max_description_length = int(os.getenv("GAME_MAX_DESCRIPTION_LENGTH", "200"))
        
        # 自动注册已配置的 LLM 提供商
        self._register_providers_from_env()
    
    def _register_providers_from_env(self):
        """从环境变量注册 LLM 提供商"""
        # 格式: (name, api_key_env, base_url_env, model_env, default_model)
        provider_configs = [
            ("qwen", "QWEN_API_KEY", "QWEN_BASE_URL", "QWEN_MODEL", "qwen3-max"),
            ("mimo", "MIMO_API_KEY", "MIMO_BASE_URL", "MIMO_MODEL", "mimo-v2-flash"),
            ("deepseek", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "deepseek-v3.2"),
            ("glm", "GLM_API_KEY", "GLM_BASE_URL", "GLM_MODEL", "glm-4.7"),
            ("kimi", "KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL", "kimi-k2-thinking"),
            ("minimax", "MINIMAX_API_KEY", "MINIMAX_BASE_URL", "MINIMAX_MODEL", "MiniMax-M2.1"),
            ("doubao", "DOUBAO_API_KEY", "DOUBAO_BASE_URL", "DOUBAO_MODEL", "doubao-seed-1-8-251228"),
        ]
        
        for name, key_env, url_env, model_env, default_model in provider_configs:
            api_key = os.getenv(key_env)
            base_url = os.getenv(url_env)
            model = os.getenv(model_env, default_model)
            
            if api_key and base_url:
                self.providers[name] = LLMProviderConfig(
                    name=name,
                    api_key=api_key,
                    base_url=base_url,
                    model=model
                )
    
    def add_provider(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.7
    ) -> None:
        """手动添加 LLM 提供商"""
        self.providers[name] = LLMProviderConfig(
            name=name,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature
        )
    
    def get_provider(self, name: str) -> Optional[LLMProviderConfig]:
        """获取提供商配置"""
        return self.providers.get(name)
    
    def list_providers(self) -> list[str]:
        """列出所有可用的提供商"""
        return list(self.providers.keys())


# 全局配置实例
config = Config()

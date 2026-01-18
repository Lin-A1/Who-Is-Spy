"""
LLM 客户端 - OpenAI 兼容 API
"""
import asyncio
import random
from typing import Optional
from openai import AsyncOpenAI
from loguru import logger


class LLMClient:
    """
    统一的 LLM 客户端
    支持任意 OpenAI 兼容 API
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        timeout: float = 30.0
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout
        )
        
        logger.debug(f"LLM 客户端初始化: {base_url} / {model}")
    
    async def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: OpenAI 格式的消息列表
            temperature: 温度参数（可选，覆盖默认值）
            max_tokens: 最大 token 数（可选，覆盖默认值）
        
        Returns:
            LLM 的回复内容
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"[LLM 请求] model={self.model}, messages={len(messages)}")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens
            )
            
            content = response.choices[0].message.content.strip()
            
            logger.debug(f"[LLM 响应] {content[:100]}...")
            
            return content
            
        except asyncio.TimeoutError:
            logger.error(f"LLM 请求超时 ({self.timeout}s)")
            raise
        except Exception as e:
            logger.error(f"LLM 请求失败: {e}")
            raise
    
    async def chat_with_retry(
        self,
        messages: list[dict],
        max_retries: int = 6,  # 增加重试次数
        **kwargs
    ) -> str:
        """带重试的聊天请求"""
        last_error = None
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                return await self.chat(messages, **kwargs)
            except Exception as e:
                last_error = e
                # 检测 429
                is_rate_limit = "429" in str(e)
                wait_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                
                if is_rate_limit:
                    logger.warning(f"⚠️ 触发限流 (429)。{wait_time:.1f}秒后重试 (第 {attempt + 1}/{max_retries} 次)...")
                else:
                    logger.warning(f"请求失败 ({e})。{wait_time:.1f}秒后重试...")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
        
        logger.error(f"❌ 最终请求失败: {last_error}")
        raise last_error
    
    async def health_check(self) -> tuple[bool, str]:
        """
        健康检查 - 验证 API 是否可用
        
        Returns:
            (success, message) - 是否成功及消息
        """
        try:
            test_messages = [
                {"role": "user", "content": "请回复'OK'"}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=test_messages,
                max_tokens=10,
                timeout=15.0
            )
            
            content = response.choices[0].message.content.strip()
            return True, f"✅ {self.model} - OK"
            
        except asyncio.TimeoutError:
            return False, f"❌ {self.model} - 超时"
        except Exception as e:
            error_msg = str(e)[:50]
            return False, f"❌ {self.model} - {error_msg}"

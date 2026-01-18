"""
词库管理
"""
import json
import random
from pathlib import Path
from typing import Optional
from loguru import logger


class WordManager:
    """词库管理器"""
    
    def __init__(self, words_file: Optional[str] = None):
        if words_file is None:
            words_file = Path(__file__).parent / "words.json"
        
        self.words_file = Path(words_file)
        self.word_pairs: list[dict] = []
        self._load_words()
    
    def _load_words(self) -> None:
        """加载词库"""
        try:
            with open(self.words_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.word_pairs = data.get("word_pairs", [])
            logger.info(f"词库加载成功，共 {len(self.word_pairs)} 组词对")
        except FileNotFoundError:
            logger.warning(f"词库文件不存在: {self.words_file}")
            self.word_pairs = []
        except json.JSONDecodeError as e:
            logger.error(f"词库文件解析错误: {e}")
            self.word_pairs = []
    
    def get_random_pair(self) -> tuple[str, str]:
        """
        随机获取一组词对
        
        Returns:
            (平民词, 卧底词)
        """
        if not self.word_pairs:
            logger.warning("词库为空，使用默认词对")
            return ("苹果", "梨")
        
        pair = random.choice(self.word_pairs)
        civilian_word = pair["civilian"]
        spy_word = pair["spy"]
        
        logger.info(f"抽取词对: 平民[{civilian_word}] vs 卧底[{spy_word}]")
        
        return (civilian_word, spy_word)
    
    def add_pair(self, civilian: str, spy: str) -> None:
        """添加词对"""
        self.word_pairs.append({
            "civilian": civilian,
            "spy": spy
        })
        logger.debug(f"添加词对: {civilian} / {spy}")
    
    def save(self) -> None:
        """保存词库到文件"""
        data = {"word_pairs": self.word_pairs}
        
        with open(self.words_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"词库已保存，共 {len(self.word_pairs)} 组词对")
    
    def get_all_pairs(self) -> list[tuple[str, str]]:
        """获取所有词对"""
        return [(p["civilian"], p["spy"]) for p in self.word_pairs]
    
    def __len__(self) -> int:
        return len(self.word_pairs)

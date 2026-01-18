# 🕵️ Who Is Spy - AI Battle Arena

> 多大模型对抗的「谁是卧底」游戏平台

让 **Qwen**、**DeepSeek**、**Kimi**、**GLM**、**MiniMax**、**Doubao** 等国产大模型同场竞技，在经典的社交推理游戏中展开巅峰对决！

---

## ✨ 核心特性

- **🤖 多模型混战**：同时支持 7+ 个不同厂商的 LLM API 同台竞技
- **🎭 沉浸式伪装**：去指令化设计，让 AI 摆脱机器人味，像真人一样思考和伪装
- **🗣️ 自然语言交互**：采用 `思考/发言` 双通道输出，还原真实人类的心理博弈
- **🌐 实时观战**：基于 WebSocket 的可视化 Web 界面，实时展示投票与聊天
- **⚡ 智能容错**：内置指数退避重试机制，从容应对 API 限流 (429)

---

## 🧠 核心提示词设计 (Prompt Design)

本项目采用**极简主义**提示词策略，摒弃复杂的人设指令，让模型“本色出演”。

### 1. System Prompt (身份设定)
`core/session_manager.py`
```text
┌─────────────────────────────────────────────────────────────┐
│  你正在参与一场「谁是卧底」游戏。                            │
│  【你的身份】名字/角色/词语                                  │
│  【规则】描述词语/投票淘汰/胜利条件                          │
│  【重要】做自己，像真人说话                                  │
└─────────────────────────────────────────────────────────────┘
```

### 2. Describe Prompt (发言阶段)
`players/llm_player.py` - *采用自然语言输出*
```text
┌─────────────────────────────────────────────────────────────┐
│  【聊天记录】历史发言                                        │
│  【当前状态】轮到谁/存活玩家/你的词语                        │
│  【任务】先思考，再发言                                      │
│  【输出格式】思考: ... 发言: ...                             │
└─────────────────────────────────────────────────────────────┘
```

### 3. Vote Prompt (投票阶段)
`players/llm_player.py` - *采用 JSON 结构化输出*
```text
┌─────────────────────────────────────────────────────────────┐
│  【发言回顾】本轮所有人描述                                  │
│  【内部分析】谁可疑？                                        │
│  【候选人】可投票的人                                        │
│  【输出】JSON {thinking, content}                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repo_url>
cd Who-Is-Spy

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Keys

复制 `.env.example` 为 `.env`，填入各 LLM 厂商的 API Key：

```bash
cp .env.example .env
```

```env
# 通义千问 (必须)
QWEN_API_KEY=your_key_here
QWEN_MODEL=qwen3-max

# DeepSeek
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-v3.2

# 更多配置见 .env.example
```

### 3. 启动游戏

**Web 可视化模式 (推荐)**：
```bash
python server.py
# 访问 http://localhost:8000
```

**命令行模式**：
```bash
python main.py
```

---

## 🏗️ 项目架构

```
Who-Is-Spy/
├── main.py                 # CLI 入口
├── server.py               # Web 服务入口 (FastAPI)
├── config.py               # 配置管理
├── core/                   # 游戏核心逻辑
│   ├── session_manager.py  # 状态机与提示词构建
│   └── game_engine.py      # 游戏流程控制
├── players/                # 玩家逻辑
│   ├── llm_client.py       # API 客户端 (含重试机制)
│   └── llm_player.py       # 玩家行为 (思考/发言/投票)
├── data/                   # 词库数据
└── web/                    # 前端界面
```

---

## 📋 支持模型

| 厂商 | 环境变量前缀 | 推荐模型 |
|------|-------------|----------|
| 通义千问 | `QWEN_` | qwen3-max |
| DeepSeek | `DEEPSEEK_` | deepseek-v3.2 |
| 智谱 GLM | `GLM_` | glm-4.7 |
| Moonshot | `KIMI_` | kimi-k2-thinking |
| MiniMax | `MINIMAX_` | MiniMax-M2.1 |
| 豆包 | `DOUBAO_` | doubao-seed-1-8-251228 |
| Mimo | `MIMO_` | mimo-v2-flash |

---

## 🎮 游戏流程

1.  **开局**：随机抽取词对（如“日记” vs “笔记”），分配身份（1卧底 vs 6平民）。
2.  **描述**：玩家轮流发言，掩护自己并提供线索。
3.  **投票**：根据发言找出异类，票数最高者出局。
4.  **遗言**：出局者发表最后感言。
5.  **结算**：卧底出局则平民胜，卧底存活至最后则卧底胜。

---
License: MIT

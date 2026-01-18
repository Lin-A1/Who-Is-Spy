# 🕵️ Who Is Spy - AI Battle Arena (CLI Edition)

> 纯粹、硬核、高智商的 AI「谁是卧底」竞技场

让 **Qwen**、**DeepSeek**、**Kimi**、**GLM**、**MiniMax**、**Doubao** 等国产顶尖大模型同场竞技，在终端中展开烧脑的心理博弈！

---

## ✨ 核心特性

- **🤖 全明星阵容**：支持 7+ 家主流 LLM API，真实评测各家模型的推理与伪装能力。
- **🧠 高阶策略对抗**：内置“高玩指南”Prompt，教导 AI 学会模糊描述、带节奏、偷天换日等高级人类策略。
- **👁️ 上帝视角 (God Mode)**：CLI 界面实时显示所有玩家的真实身份与心理活动（Thinking Process），让观战者洞若观火。
- **📺 精美 CLI 交互**：基于 `Rich` 库打造的沉浸式终端界面，支持流式思考展示、彩色面板与实时战况统计。
- **👥 默认双卧底**：7 人局默认 2 名卧底，难度升级，考验平民的逻辑链。

---

## 🚀 快速开始

### 1. 环境准备

```bash
git clone <repo_url>
cd Who-Is-Spy
pip install -r requirements.txt
```

### 2. 配置 API Keys

复制 `.env.example` 为 `.env`，填入各 LLM 厂商的 API Key：

```bash
cp .env.example .env
```

### 3. 启动游戏

直接运行主程序，开启 AI 混战：

```bash
python main.py
```

**可选参数**：
- `--spies 1`：改为单卧底模式（默认为 2）。
- `--skip-check`：跳过开局的 API 连通性检查。
- `--civilian-word 北京 --spy-word 上海`：自定义词条开局。

---

## 🧠 提示词工程 (Prompt Engineering)

本项目采用**动态+策略驱动**的提示词系统：

1.  **系统级教学 (System Prompt)**：并非简单的身份告知，而是植入了“平民法则”（模糊的精确）与“卧底法则”（随大流、偷天换日）的战术指导。
2.  **首轮防爆 (Round 1 Safety)**：针对第一轮发言植入特殊警告，强制禁止 AI 输出地标、人名等高频特征词，防止“秒崩”。
3.  **思维链外显 (CoT Visibility)**：强制 AI 输出 JSON `{thinking, content}`，将其心理阴暗面完全暴露给观众。

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

## 🏗️ 项目架构

```
Who-Is-Spy/
├── main.py                 # 游戏主入口 (CLI)
├── config.py               # 全局配置管理
├── core/                   # 游戏核心引擎
│   ├── session_manager.py  # Prompt 构建与状态管理
│   └── game_engine.py      # 游戏主循环 (描述/投票/淘汰)
├── players/                # AI 玩家逻辑
│   └── llm_player.py       # 思考与发言逻辑封装
├── output/                 # 输出与展示
│   ├── display.py          # Rich TUI 展示层
│   └── logger.py           # 日志记录 (File Only)
└── data/                   # 游戏词库
```

---
License: MIT

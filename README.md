# AgenticGroupCR - 多 AI 引擎 Code Review 工具

这是一个独立的 code review 工具，支持使用多种 AI 引擎（Claude Code、Codex）进行代码审查。

## 功能特性

- **多 AI 引擎支持**：
  - **Claude Code**：通过 `claude -p` 命令调用，支持仓库上下文访问，支持临时指定模型
  - **Codex**：通过 `codex exec` 命令调用，支持临时指定模型和推理程度
- **三种分析模式**：
  - `review` - 代码审查：识别代码问题和改进建议
  - `analyze` - 变更解析：理解变更目的、影响范围和架构影响
  - `priority` - 优先级评估：识别最需要 review 的代码部分和预估时长
- **并行执行**：`all` 模式下三种分析并行执行，大幅提升效率
- **智能 JSON 提取**：自动处理重复 JSON 输出问题
- 根据 appid 自动查找 `~/VibeCoding/apprepo/` 下的 git 项目
- 对齐 Codex 的 git diff 处理逻辑（包括 merge-base 计算、upstream 检测等）
- 自动加载 review rubric（review_prompt.md）
- 生成结构化的 review prompt
- 支持大文件截断（对齐 Codex 的截断策略）
- 自动保存 prompt 和 review 结果到时间戳目录
- 生成综合 HTML 报告（支持 Tab 切换）
- **Claude 默认启用仓库上下文访问**：Claude 在目标仓库目录下运行，可以访问完整的代码

## 安装

### 前置要求

1. **Python 3**（通常系统自带）：
```bash
python3 --version  # 验证是否已安装
```

2. **选择 AI 引擎**（至少安装一个）：

   **选项 A: Claude Code**
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

   **选项 B: Codex**
   ```bash
   # 参考 https://github.com/openai/codex 安装
   ```

3. **Git**（通常系统自带）：
```bash
git --version  # 验证是否已安装
```

## 快速开始

### 使用 Claude Code

```bash
# 完整分析（三种模式并行执行）
./run.sh -a 100027304 -b main -t feature/my-feature

# 使用 Opus 模型
./run.sh -a 100027304 -b main -t feature/my-feature -M opus
```

### 使用 Codex

```bash
# 完整分析（三种模式并行执行）
./run_codex.sh -a 100027304 -b main -t feature/my-feature

# 使用指定模型和推理程度
./run_codex.sh -a 100027304 -b main -t feature/my-feature -M gpt-5.1-codex-max -r high
```

## 参数说明

### Claude Code 参数（claude_cr.py / run.sh）

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--appid` | `-a` | 应用 ID（必需） | - |
| `--basebranch` | `-b` | 基准分支名称（必需） | - |
| `--targetbranch` | `-t` | 目标分支名称（必需） | - |
| `--search-root` | `-s` | 搜索根目录 | `~/VibeCoding/apprepo` |
| `--mode` | `-m` | 运行模式 | `all` |
| `--model` | `-M` | 指定模型（临时） | - |
| `--no-context` | - | 禁用仓库上下文访问 | 启用 |
| `--prompt-only` | - | 只生成 prompt，不调用 Claude | - |

**运行模式**：
- `all` - 完整分析（analyze + priority + review，并行执行）
- `review` - 仅代码审查
- `analyze` - 仅变更解析
- `priority` - 仅优先级评估

**可用模型**：
- `sonnet` - Claude Sonnet 4.5（推荐）
- `opus` - Claude Opus 4.5（最强）
- `haiku` - Claude Haiku（快速）

### Codex 参数（codex_cr.py / run_codex.sh）

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--appid` | `-a` | 应用 ID（必需） | - |
| `--basebranch` | `-b` | 基准分支名称（必需） | - |
| `--targetbranch` | `-t` | 目标分支名称（必需） | - |
| `--search-root` | `-s` | 搜索根目录 | `~/VibeCoding/apprepo` |
| `--mode` | `-m` | 运行模式 | `all` |
| `--model` | `-M` | 指定模型（临时） | - |
| `--profile` | `-p` | 使用 Codex Profile | - |
| `--reasoning-effort` | `-r` | 推理努力程度 | `medium` |
| `--no-context` | - | 禁用仓库上下文访问 | 启用 |
| `--prompt-only` | - | 只生成 prompt，不调用 Codex | - |

**可用模型**：
- `gpt-5.1-codex-max` - 最强编码模型（支持 xhigh 推理）
- `gpt-5.1` - GPT-5.1 标准版
- `o3` - OpenAI o3 推理模型
- `o4-mini` - OpenAI o4-mini 推理模型
- `gpt-4o` - GPT-4o 模型

**推理努力程度**：
- `minimal` - 最小推理
- `low` - 低推理
- `medium` - 中等推理（默认）
- `high` - 高推理
- `xhigh` - 最高推理（仅 gpt-5.1-codex-max 支持）

## 使用示例

### Claude Code 示例

```bash
# 1. 完整分析（默认，三种模式并行执行）
./run.sh -a 100027304 -b main -t feature/add-new-api

# 2. 使用 Opus 模型进行分析
./run.sh -a 100027304 -b main -t feature/add-new-api -M opus

# 3. 仅代码审查
./run.sh -a 100027304 -b main -t feature/add-new-api -m review

# 4. 禁用仓库上下文访问
./run.sh -a 100027304 -b main -t feature/add-new-api --no-context

# 5. 只生成 prompt（不调用 Claude）
./run.sh -a 100027304 -b main -t feature/add-new-api --prompt-only
```

### Codex 示例

```bash
# 1. 完整分析（默认，三种模式并行执行）
./run_codex.sh -a 100027304 -b main -t feature/add-new-api

# 2. 使用指定模型和高推理程度
./run_codex.sh -a 100027304 -b main -t feature/add-new-api -M gpt-5.1-codex-max -r high

# 3. 使用 o3 模型
./run_codex.sh -a 100027304 -b main -t feature/add-new-api -M o3

# 4. 使用 o3 Profile（包含预设参数）
./run_codex.sh -a 100027304 -b main -t feature/add-new-api -p o3

# 5. 仅代码审查，使用最高推理
./run_codex.sh -a 100027304 -b main -t feature/add-new-api -m review -M gpt-5.1-codex-max -r xhigh

# 6. 只生成 prompt（不调用 Codex）
./run_codex.sh -a 100027304 -b main -t feature/add-new-api --prompt-only
```

## 输出说明

### 输出目录

- **Claude Code**: `review-prompt-{timestamp}/`
- **Codex**: `codex-review-{timestamp}/`

### 输出文件

| 文件 | 说明 |
|------|------|
| `prompt_*.txt` | 生成的完整 prompt |
| `meta.txt` | 元信息（appid, branches, 模型, 时间戳等） |
| `raw_output.txt` | AI 的原始输出 |
| `change_analysis.json` | 变更解析结果 |
| `review_priority.json` | 优先级评估结果 |
| `review_result.json` | 代码审查结果 |
| `change_analysis.html` | 变更解析 HTML 报告 |
| `review_priority.html` | 优先级评估 HTML 报告 |
| `review_result.html` | 代码审查 HTML 报告 |
| `report.html` | **综合报告（支持 Tab 切换，推荐）** |

### 查看报告

```bash
# 打开综合报告（推荐）
open codex-review-20251217_004126/report.html

# 或分别查看各报告
open codex-review-20251217_004126/change_analysis.html
open codex-review-20251217_004126/review_priority.html
open codex-review-20251217_004126/review_result.html
```

## 三种分析模式详解

### 1. 变更解析（analyze）

分析代码变更的目的、影响范围和架构影响。输出包含：
- 变更摘要
- 文件级别的变更分析
- 架构影响评估
- 迁移注意事项

### 2. 优先级评估（priority）

识别最需要 review 的代码部分，帮助 reviewer 合理分配时间。输出包含：
- Review 摘要（文件数、预估时间、复杂度评分）
- 优先级区域（高/中/低优先级文件及原因）
- 推荐的 review 顺序
- 并行 review 分组建议

### 3. 代码审查（review）

识别代码问题和改进建议。输出包含：
- 问题列表（按优先级 P0-P3 分类）
- 每个问题的详细描述、代码位置、置信度
- 整体评估和建议

## 并行执行

当使用 `all` 模式时，三种分析会**并行执行**，大幅提升效率：

```
串行执行: T1 + T2 + T3
并行执行: max(T1, T2, T3)  ← 约 3 倍提升
```

执行过程中会显示各模式的进度：
```
==================================================
并行运行 3 个模式: analyze, priority, review (Codex)
仓库上下文: 已启用（工作目录: /path/to/repo）
==================================================

[analyze] 开始分析...
[priority] 开始分析...
[review] 开始分析...
[analyze] ✓ 输出格式验证通过
[analyze] ✓ 分析完成
[priority] ✓ 分析完成
[review] ✓ 分析完成

==================================================
执行结果摘要:
==================================================
  [analyze] ✓ 成功
  [priority] ✓ 成功
  [review] ✓ 成功
```

## 模型配置说明

### 临时 vs 持久化

命令行指定的模型参数是**临时的**，只对当前执行有效，不会修改配置文件。

```bash
# 临时使用 opus 模型（不影响配置文件）
./run.sh -a 100027304 -b main -t feature/test -M opus
```

### Codex 配置优先级

```
1. 命令行参数 --model / -M（最高优先级，临时）
2. ~/.codex/config.toml 中的 model 配置（持久化）
3. Codex CLI 内置默认值 gpt-5.1-codex-max（最低优先级）
```

## 项目结构

```
AgenticGroupCR/
├── claude_cr.py               # Claude Code 主入口（支持并行执行）
├── codex_cr.py                # Codex 主入口（支持并行执行）
├── repo_finder.py             # 仓库查找模块（共享）
├── git_utils.py               # Git 操作工具（共享）
├── prompt_utils.py            # Prompt 构建工具（共享）
├── json_utils.py              # JSON 处理工具（支持重复 JSON 提取）
├── generate_report.py         # HTML 报告生成（支持综合报告）
├── run.sh                     # Claude 便捷运行脚本
├── run_codex.sh               # Codex 便捷运行脚本
├── review_prompt.md           # Code review 规范
├── change_analysis_prompt.md  # 变更解析 prompt
├── review_priority_prompt.md  # 优先级评估 prompt
└── README.md                  # 本文档
```

## 故障排除

### 1. 找不到 claude 命令

```bash
npm install -g @anthropic-ai/claude-code
```

或使用 `--prompt-only` 参数只生成 prompt。

### 2. 找不到 codex 命令

参考 https://github.com/openai/codex 安装，或使用 `--prompt-only` 参数。

### 3. 找不到项目

检查：
- `~/VibeCoding/apprepo/` 目录是否存在
- 项目中是否有 `app.properties` 文件
- `app.properties` 中是否包含正确的 `app.id` 配置

### 4. JSON 解析失败

工具会自动处理重复 JSON 输出问题（如 `}{` 拼接）。如果仍然失败，可以查看 `raw_output.txt` 了解原始输出。

### 5. 报告显示"暂无数据"

可能是 JSON 文件损坏。可以手动修复：

```python
python3 -c "
from json_utils import extract_first_json_object
import json

with open('change_analysis.json', 'r') as f:
    content = f.read()
json_str = extract_first_json_object(content)
if json_str:
    data = json.loads(json_str)
    with open('change_analysis.json', 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('已修复')
"
```

## License

与 Codex 项目保持一致。

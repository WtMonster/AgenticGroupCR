# Claude Code Review Tool

这是一个独立的 code review 工具，可以让其他 AI 编程工具也能使用 Codex 的 review 能力。

## 功能特性

- 根据 appid 自动查找 `~/VibeCoding/apprepo/` 下的 git 项目
- 对齐 Codex 的 git diff 处理逻辑（包括 merge-base 计算、upstream 检测等）
- 自动加载 Codex 的 review rubric（review_prompt.md）
- 生成结构化的 review prompt 并调用 Claude Code
- 支持大文件截断（对齐 Codex 的截断策略）
- 自动保存 prompt 和 review 结果到时间戳目录
- 完整的 JSON 输出验证和错误处理
- **默认启用仓库上下文访问**：Claude 在目标仓库目录下运行，可以访问完整的代码

## 安装

### 前置要求

1. **Python 3**（通常系统自带）：
```bash
python3 --version  # 验证是否已安装
```

2. **Claude Code**：
```bash
npm install -g @anthropic-ai/claude-code
```

3. **Git**（通常系统自带）：
```bash
git --version  # 验证是否已安装
```

## 使用方法

### 方式一：使用便捷脚本（推荐）

```bash
./run.sh -a 100027304 -b main -t feature/my-feature
```

脚本会自动检查依赖并运行 code review。**默认情况下，Claude 会在目标仓库目录下运行，可以访问完整代码。**

### 方式二：直接运行 Python 脚本

```bash
python3 claude_cr.py \
  --appid 100027304 \
  --basebranch main \
  --targetbranch feature/my-feature
```

### 参数说明

- `--appid, -a`: 应用 ID（必需）
- `--basebranch, -b`: 基准分支名称（必需）
- `--targetbranch, -t`: 目标分支名称（必需）
- `--search-root, -s`: 搜索根目录（默认：`~/VibeCoding/apprepo`）
- `--mode, -m`: 运行模式（默认：`all`）
  - `all`: 完整分析（analyze + priority + review）
  - `review`: 仅代码审查
  - `analyze`: 仅变更解析
  - `priority`: 仅优先级评估
- `--no-context`: 禁用仓库上下文访问（默认启用）
- `--prompt-only, -p`: 只生成 prompt，不调用 Claude

### 示例

#### 1. 完整的 code review 流程（默认启用仓库上下文）

```bash
./run.sh -a 100027304 -b main -t feature/add-new-api
```

Claude 会在目标仓库目录下运行，可以：
- 使用 Read 工具读取任何文件的完整内容
- 使用 Grep 工具搜索代码
- 使用 Glob 工具查找文件
- 使用 Bash 工具执行 git 命令

这样 Claude 可以更准确地理解代码上下文，给出更高质量的 review。

#### 2. 禁用仓库上下文访问

```bash
./run.sh -a 100027304 -b main -t feature/add-new-api --no-context
```

#### 3. 只生成 prompt（不调用 Claude）

```bash
./run.sh -a 100027304 -b main -t feature/add-new-api --prompt-only
```

#### 4. 自定义搜索目录

```bash
python3 claude_cr.py \
  --appid 100027304 \
  --basebranch main \
  --targetbranch feature/add-new-api \
  --search-root /custom/repo/path
```

## 仓库上下文访问模式

### 什么是仓库上下文访问？

**默认情况下**，Claude 不仅能看到 git diff 中的代码变更，还能访问完整的仓库代码。这让 Claude 可以：
- 查看被修改函数/类的完整实现
- 检查调用关系和依赖
- 理解相关的测试代码
- 了解项目的架构设计

### 工作原理

工具会：
1. 根据 appid 找到目标仓库
2. 将 Claude 的工作目录切换到该仓库
3. 在 prompt 中告知 Claude 可以使用 Read/Grep/Glob 等工具
4. Claude 会主动探索代码以理解上下文

### 对比示例

**禁用仓库上下文（--no-context）**：
```
Claude 只能看到 diff 中的代码，可能无法判断某个函数调用是否安全
```

**启用仓库上下文（默认）**：
```
Claude 可以读取被调用函数的完整实现，确认其行为和边界条件
```

## 工作原理

### 1. 查找 Git 项目

工具会在指定的搜索根目录（默认 `~/VibeCoding/apprepo/`）下递归查找 `app.properties` 文件，并匹配其中的 `app.id` 配置项。找到匹配的项目后，会定位到该项目的 git 仓库根目录。

### 2. Git Diff 处理

对齐 Codex 的处理逻辑：

- 使用 `git rev-parse` 解析分支的 SHA
- 检查 base branch 是否有 upstream，且 remote ahead
- 如果 remote ahead，优先使用 upstream 作为 base
- 使用 `git merge-base` 计算合并基准点
- 生成 `git diff --name-status` 和 `git diff` 输出

### 3. Prompt 构建

- 自动加载 review rubric（优先使用本地 `review_prompt.md`，否则向上查找 `codex-rs/core/review_prompt.md`）
- 拼接 rubric + MR diff 信息
- 包含完整的元信息（appid, repo root, branches, SHAs 等）
- 支持大文件截断（保留头部和尾部，中间插入截断标记）
- 默认在 prompt 中添加工具使用说明，告知 Claude 可以访问仓库代码

### 4. Claude 调用

- 通过 stdin 将 prompt 传递给 `claude -p -` 命令
- 默认在目标仓库目录下运行 Claude，使其可以访问完整代码
- 返回 Claude 的 review 结果（JSON 格式）

## 输出格式

工具会自动保存结果到时间戳目录（例如 `review-prompt-20251215_104656/`），包含：

- `prompt_*.txt` - 生成的完整 prompt
- `meta.txt` - 元信息（appid, branches, 时间戳等）
- `raw_output.txt` - Claude 的原始输出
- `review_result.json` - 解析后的 JSON 结果
- `*.html` - 可视化的 HTML 报告

JSON 格式示例：

```json
{
  "findings": [
    {
      "title": "[P1] 问题标题",
      "body": "问题详细描述",
      "confidence_score": 0.9,
      "code_location": {
        "absolute_file_path": "/path/to/file.py",
        "line_range": {"start": 10, "end": 15}
      }
    }
  ],
  "overall_correctness": "patch is correct",
  "overall_explanation": "整体评估说明",
  "overall_confidence_score": 0.85
}
```

## 项目结构

```
claude-cr/
├── claude_cr.py               # 主入口文件
├── repo_finder.py             # 仓库查找模块
├── git_utils.py               # Git 操作工具
├── prompt_utils.py            # Prompt 构建工具
├── json_utils.py              # JSON 处理工具
├── generate_report.py         # HTML 报告生成
├── run.sh                     # 便捷运行脚本
├── review_prompt.md           # Code review 规范
├── change_analysis_prompt.md  # 变更解析 prompt
├── review_priority_prompt.md  # 优先级评估 prompt
└── README.md                  # 本文档
```

## 对齐 Codex 的实现细节

### Git 操作对齐

- ✅ 支持 upstream 检测和 remote ahead 判断
- ✅ 使用 `git merge-base` 计算合并基准点
- ✅ 生成 `--name-status` 和完整 diff

### 截断策略对齐

- ✅ name-status 最大 200,000 字符
- ✅ diff 最大 400,000 字符
- ✅ 保留头部和尾部，中间插入截断标记

### Review Rubric 对齐

- ✅ 自动加载 `codex-rs/core/review_prompt.md`
- ✅ 使用相同的 JSON output schema
- ✅ 包含优先级标记（P0-P3）

## 故障排除

### 1. 找不到 claude 命令

确保已安装 Claude Code：
```bash
npm install -g @anthropic-ai/claude-code
```

或者使用 `--prompt-only` 参数只生成 prompt，不调用 Claude。

### 2. 找不到项目

检查：
- `~/VibeCoding/apprepo/` 目录是否存在
- 项目中是否有 `app.properties` 文件
- `app.properties` 中是否包含正确的 `app.id` 配置

### 3. Git 命令失败

确保：
- 项目是一个有效的 git 仓库
- 指定的分支名称正确
- 有权限访问 git 仓库

### 4. JSON 解析失败

工具会自动尝试从 Claude 输出中提取 JSON，如果失败会创建后备结果。
可以查看 `raw_output.txt` 文件了解原始输出内容。

## 开发和调试

### 查看生成的 prompt

```bash
./run.sh -a 100027304 -b main -t feature/test --prompt-only
```

### 查看完整输出

所有中间结果都保存在时间戳目录中：
```bash
ls review-prompt-20251215_104656/
# prompt_*.txt - 完整 prompt
# meta.txt - 元信息
# raw_output.txt - Claude 原始输出
# review_result.json - 解析后的结果
# *.html - HTML 报告
```

## License

与 Codex 项目保持一致。

"""
Prompt 构建工具模块
提供 review prompt 构建、rubric 加载等功能
"""

from pathlib import Path
from typing import Tuple, Dict
from datetime import datetime

# 常量
CODEX_REVIEW_PROMPT_PATH = "codex-rs/core/review_prompt.md"
NAME_STATUS_MAX_CHARS = 200_000
DIFF_MAX_CHARS = 400_000


def load_prompt_template(template_name: str) -> str:
    """
    加载 prompt 模板

    优先使用脚本同目录下的模板文件，
    否则向上查找 codex-rs/core/ 目录

    Args:
        template_name: 模板文件名（如 "review_prompt.md"）

    Returns:
        模板内容，如果未找到则返回空字符串
    """
    # 1. 优先使用脚本同目录下的模板
    script_dir = Path(__file__).parent
    local_template = script_dir / template_name
    if local_template.exists():
        with open(local_template, 'r', encoding='utf-8') as f:
            return f.read().strip()

    # 2. 向上查找 codex-rs/core/ 目录
    cwd = Path.cwd()
    current = cwd
    while current:
        candidate = current / "codex-rs" / "core" / template_name
        if candidate.exists():
            with open(candidate, 'r', encoding='utf-8') as f:
                return f.read().strip()
        parent = current.parent
        if parent == current:
            break
        current = parent

    return ""


def load_review_rubric() -> str:
    """
    加载 review rubric

    Returns:
        rubric 内容，如果未找到则返回空字符串
    """
    return load_prompt_template("review_prompt.md")


def load_change_analysis_prompt() -> str:
    """
    加载代码变更解析 prompt

    Returns:
        prompt 内容，如果未找到则返回空字符串
    """
    return load_prompt_template("change_analysis_prompt.md")


def load_review_priority_prompt() -> str:
    """
    加载 review 优先级评估 prompt

    Returns:
        prompt 内容，如果未找到则返回空字符串
    """
    return load_prompt_template("review_priority_prompt.md")


def build_mr_prompt(
    appid: str,
    base_branch: str,
    target_branch: str,
    repo_root: Path,
    comparison: dict,
    name_status: Tuple[str, bool, int, int],
    diff: Tuple[str, bool, int, int],
    with_context: bool = False
) -> str:
    """
    构建 MR diff prompt

    Args:
        appid: 应用 ID
        base_branch: 基准分支
        target_branch: 目标分支
        repo_root: 仓库根目录
        comparison: 分支比较信息
        name_status: name-status 输出 (内容, 是否截断, 总行数, 总字符数)
        diff: diff 输出 (内容, 是否截断, 总行数, 总字符数)
        with_context: 是否启用仓库上下文访问模式

    Returns:
        构建的 prompt
    """
    if with_context:
        prompt = "请对以下 Merge Request 做 code review。\n\n"
        prompt += "**重要提示**: 你现在运行在 Claude Code 环境中，当前工作目录已切换到目标仓库，你可以：\n"
        prompt += "- 使用 Read 工具读取任何文件的完整内容\n"
        prompt += "- 使用 Grep 工具搜索代码\n"
        prompt += "- 使用 Glob 工具查找文件\n"
        prompt += "- 使用 Bash 工具执行 git 命令\n\n"
        prompt += "**请充分利用这些工具来理解代码上下文**，特别是：\n"
        prompt += "- 查看被修改函数/类的完整实现\n"
        prompt += "- 检查调用关系和依赖\n"
        prompt += "- 理解相关的测试代码\n"
        prompt += "- 了解项目的架构设计\n\n"
    else:
        prompt = "请对以下 Merge Request 做 code review，仅基于下面提供的信息给出问题与建议。\n\n"

    prompt += "基本信息：\n"
    prompt += f"- appid: {appid}\n"
    prompt += f"- repoRoot: {repo_root}\n"
    prompt += f"- baseBranch: {base_branch}\n"
    prompt += f"- targetBranch: {target_branch}\n"
    prompt += f"- baseRefUsed: {comparison['base_ref_used']}\n"
    prompt += f"- baseSha: {comparison['base_sha']}\n"
    prompt += f"- targetSha: {comparison['target_sha']}\n"
    prompt += f"- mergeBaseSha: {comparison['merge_base_sha']}\n\n"

    prompt += "若需要在本地复现 diff，可运行：\n"
    prompt += f"- git merge-base {comparison['base_sha']} {comparison['target_sha']}\n"
    prompt += f"- git diff --name-status --no-color {comparison['merge_base_sha']}..{comparison['target_sha']}\n"
    prompt += f"- git diff --no-color {comparison['merge_base_sha']}..{comparison['target_sha']}\n\n"

    ns_content, ns_truncated, ns_lines, ns_chars = name_status
    prompt += "变更文件（git diff --name-status）：\n"
    prompt += ns_content.strip()
    if ns_truncated:
        prompt += f"\n[注意] name-status 输出已截断（maxChars={NAME_STATUS_MAX_CHARS}，originalLines={ns_lines}）。\n"
    prompt += "\n\n"

    diff_content, diff_truncated, diff_lines, diff_chars = diff
    prompt += "Unified diff（git diff，可能截断）：\n"
    prompt += "```diff\n"
    prompt += diff_content
    if not diff_content.endswith('\n'):
        prompt += '\n'
    prompt += "```\n"
    if diff_truncated:
        prompt += f"[注意] diff 输出已截断（maxChars={DIFF_MAX_CHARS}，originalLines={diff_lines}）。\n"
        if with_context:
            prompt += "你可以使用 Read 工具查看完整文件内容，或使用 Bash 执行 git 命令获取完整 diff。\n"
        else:
            prompt += "请优先根据现有 diff 识别高风险问题；如需完整 diff，可在仓库中执行上述 git 命令。\n"

    return prompt


def build_full_prompt(
    appid: str,
    base_branch: str,
    target_branch: str,
    repo_root: Path,
    comparison: dict,
    name_status: Tuple[str, bool, int, int],
    diff: Tuple[str, bool, int, int],
    with_context: bool = False
) -> str:
    """
    构建完整的 review prompt（包含 rubric + MR diff）

    Args:
        appid: 应用 ID
        base_branch: 基准分支
        target_branch: 目标分支
        repo_root: 仓库根目录
        comparison: 分支比较信息
        name_status: name-status 输出
        diff: diff 输出
        with_context: 是否启用仓库上下文访问模式

    Returns:
        完整的 prompt
    """
    print("正在构建 prompt...")

    # 加载 review rubric
    rubric = load_review_rubric()

    # 构建 MR prompt
    mr_prompt = build_mr_prompt(
        appid, base_branch, target_branch,
        repo_root, comparison, name_status, diff, with_context
    )

    # 如果找到了 rubric，拼接在前面
    if rubric:
        full_prompt = rubric + "\n\n"
        full_prompt += "-----\n\n"
        full_prompt += "以下是需要 review 的 MR diff 信息：\n\n"
        full_prompt += mr_prompt
        return full_prompt

    return mr_prompt


def save_prompt_to_file(
    prompt: str,
    appid: str,
    base_branch: str,
    target_branch: str,
    repo_root: Path,
    mode: str = "review"
) -> Path:
    """
    保存 prompt 到文件，返回输出目录路径

    Args:
        prompt: prompt 内容
        appid: 应用 ID
        base_branch: 基准分支
        target_branch: 目标分支
        repo_root: 仓库根目录
        mode: 运行模式（用于命名 prompt 文件）

    Returns:
        输出目录路径
    """
    # 生成时间戳目录名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"review-prompt-{timestamp}"

    # 在找到的 git 项目根目录下创建输出目录
    output_dir = repo_root / dir_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存 prompt（使用 prompt_{mode}.txt 格式）
    prompt_file = output_dir / f'prompt_{mode}.txt'
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    # 保存元信息
    meta_file = output_dir / 'meta.txt'
    with open(meta_file, 'w', encoding='utf-8') as f:
        f.write(f"AppID: {appid}\n")
        f.write(f"Base Branch: {base_branch}\n")
        f.write(f"Target Branch: {target_branch}\n")
        f.write(f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    return output_dir


def build_change_analysis_prompt(
    appid: str,
    base_branch: str,
    target_branch: str,
    repo_root: Path,
    comparison: dict,
    name_status: Tuple[str, bool, int, int],
    diff: Tuple[str, bool, int, int],
    with_context: bool = False
) -> str:
    """
    构建代码变更解析 prompt

    Args:
        appid: 应用 ID
        base_branch: 基准分支
        target_branch: 目标分支
        repo_root: 仓库根目录
        comparison: 分支比较信息
        name_status: name-status 输出
        diff: diff 输出
        with_context: 是否启用仓库上下文访问模式

    Returns:
        完整的 prompt
    """
    print("正在构建代码变更解析 prompt...")

    # 加载 change analysis prompt
    template = load_change_analysis_prompt()

    # 构建 MR 基本信息
    mr_info = build_mr_prompt(
        appid, base_branch, target_branch,
        repo_root, comparison, name_status, diff, with_context
    )

    # 拼接完整 prompt
    if template:
        full_prompt = template + "\n\n"
        full_prompt += "-----\n\n"
        full_prompt += "以下是需要分析的 MR diff 信息：\n\n"
        full_prompt += mr_info
        return full_prompt

    return mr_info


def build_review_priority_prompt(
    appid: str,
    base_branch: str,
    target_branch: str,
    repo_root: Path,
    comparison: dict,
    name_status: Tuple[str, bool, int, int],
    diff: Tuple[str, bool, int, int],
    with_context: bool = False
) -> str:
    """
    构建 review 优先级评估 prompt

    Args:
        appid: 应用 ID
        base_branch: 基准分支
        target_branch: 目标分支
        repo_root: 仓库根目录
        comparison: 分支比较信息
        name_status: name-status 输出
        diff: diff 输出
        with_context: 是否启用仓库上下文访问模式

    Returns:
        完整的 prompt
    """
    print("正在构建 review 优先级评估 prompt...")

    # 加载 review priority prompt
    template = load_review_priority_prompt()

    # 构建 MR 基本信息
    mr_info = build_mr_prompt(
        appid, base_branch, target_branch,
        repo_root, comparison, name_status, diff, with_context
    )

    # 拼接完整 prompt
    if template:
        full_prompt = template + "\n\n"
        full_prompt += "-----\n\n"
        full_prompt += "以下是需要评估的 MR diff 信息：\n\n"
        full_prompt += mr_info
        return full_prompt

    return mr_info

"""
Git 操作工具模块
提供 Git 命令执行、分支比较、diff 生成等功能
"""

import subprocess
from pathlib import Path
from typing import Tuple, Dict

# 截断配置
NAME_STATUS_MAX_CHARS = 200_000
DIFF_MAX_CHARS = 400_000


def run_git(repo_root: Path, args: list, max_chars: int = 10_000) -> Tuple[str, bool, int, int]:
    """
    运行 git 命令并返回输出（支持截断）

    Args:
        repo_root: git 仓库根目录
        args: git 命令参数列表
        max_chars: 最大字符数，超过则截断

    Returns:
        (输出内容, 是否截断, 总行数, 总字符数)

    Raises:
        Exception: git 命令执行失败
    """
    result = subprocess.run(
        ['git'] + args,
        cwd=repo_root,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"git 命令失败: git {' '.join(args)}\n错误: {result.stderr}")

    output = result.stdout
    total_chars = len(output)
    total_lines = output.count('\n')

    # 实现截断逻辑
    truncated = False
    if total_chars > max_chars:
        left_budget = max_chars // 2
        right_budget = max_chars - left_budget

        prefix = output[:left_budget]
        suffix = output[-right_budget:]
        removed_chars = total_chars - max_chars

        output = f"{prefix}…{removed_chars} chars truncated…{suffix}"
        truncated = True

    return output, truncated, total_lines, total_chars


def resolve_ref(repo_root: Path, ref_name: str) -> str:
    """
    解析 ref 到 SHA，自动处理本地分支和远程分支

    Args:
        repo_root: git 仓库根目录
        ref_name: 分支名称或 ref

    Returns:
        解析后的 SHA

    Raises:
        Exception: 无法解析分支
    """
    # 尝试直接解析
    try:
        sha, _, _, _ = run_git(repo_root, ['rev-parse', '--verify', ref_name])
        return sha.strip()
    except Exception:
        pass

    # 尝试作为远程分支解析
    try:
        sha, _, _, _ = run_git(repo_root, ['rev-parse', '--verify', f'origin/{ref_name}'])
        return sha.strip()
    except Exception:
        pass

    # 尝试作为 remotes/origin/ 解析
    try:
        sha, _, _, _ = run_git(repo_root, ['rev-parse', '--verify', f'remotes/origin/{ref_name}'])
        return sha.strip()
    except Exception:
        raise Exception(f"无法解析分支: {ref_name}")


def resolve_branch_comparison(repo_root: Path, base_branch: str, target_branch: str) -> dict:
    """
    解析分支比较信息，对齐 codex 逻辑

    Args:
        repo_root: git 仓库根目录
        base_branch: 基准分支名称
        target_branch: 目标分支名称

    Returns:
        包含分支比较信息的字典，包含以下键：
        - base_ref_used: 实际使用的 base ref
        - base_sha: base 分支的 SHA
        - target_sha: target 分支的 SHA
        - merge_base_sha: merge-base SHA
    """
    print("正在获取 git diff 信息...")

    # 1. 解析 base branch 的 SHA
    base_sha = resolve_ref(repo_root, base_branch)
    base_ref_used = base_branch

    # 2. 检查是否有 upstream，且 remote ahead
    try:
        upstream, _, _, _ = run_git(
            repo_root,
            ['rev-parse', '--abbrev-ref', '--symbolic-full-name', f'{base_branch}@{{upstream}}']
        )
        upstream = upstream.strip()

        if upstream:
            # 检查 remote 是否 ahead
            counts, _, _, _ = run_git(
                repo_root,
                ['rev-list', '--left-right', '--count', f'{base_branch}...{upstream}']
            )
            parts = counts.strip().split()
            if len(parts) >= 2 and int(parts[1]) > 0:
                # Remote ahead，使用 upstream
                try:
                    upstream_sha, _, _, _ = run_git(repo_root, ['rev-parse', '--verify', upstream])
                    base_ref_used = upstream
                    base_sha = upstream_sha.strip()
                except Exception:
                    pass
    except Exception:
        pass

    # 3. 解析 target branch 的 SHA
    target_sha = resolve_ref(repo_root, target_branch)

    # 4. 计算 merge-base
    merge_base_sha, _, _, _ = run_git(repo_root, ['merge-base', target_sha, base_sha])
    merge_base_sha = merge_base_sha.strip()

    return {
        'base_ref_used': base_ref_used,
        'base_sha': base_sha,
        'target_sha': target_sha,
        'merge_base_sha': merge_base_sha
    }


def get_name_status(repo_root: Path, comparison: dict) -> Tuple[str, bool, int, int]:
    """
    获取 name-status 输出

    Args:
        repo_root: git 仓库根目录
        comparison: 分支比较信息

    Returns:
        (输出内容, 是否截断, 总行数, 总字符数)
    """
    range_spec = f"{comparison['merge_base_sha']}..{comparison['target_sha']}"
    return run_git(
        repo_root,
        ['diff', '--name-status', '--no-color', range_spec],
        NAME_STATUS_MAX_CHARS
    )


def get_diff(repo_root: Path, comparison: dict) -> Tuple[str, bool, int, int]:
    """
    获取完整 diff 输出

    Args:
        repo_root: git 仓库根目录
        comparison: 分支比较信息

    Returns:
        (输出内容, 是否截断, 总行数, 总字符数)
    """
    range_spec = f"{comparison['merge_base_sha']}..{comparison['target_sha']}"
    return run_git(
        repo_root,
        ['diff', '--no-color', range_spec],
        DIFF_MAX_CHARS
    )


def get_git_status(repo_root: Path) -> str:
    """
    获取 git status 输出

    Args:
        repo_root: git 仓库根目录

    Returns:
        git status 输出
    """
    output, _, _, _ = run_git(repo_root, ['status', '--short'])
    return output


def get_current_branch(repo_root: Path) -> str:
    """
    获取当前分支名称

    Args:
        repo_root: git 仓库根目录

    Returns:
        当前分支名称
    """
    output, _, _, _ = run_git(repo_root, ['rev-parse', '--abbrev-ref', 'HEAD'])
    return output.strip()

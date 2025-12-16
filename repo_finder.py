"""
仓库查找模块
提供根据 appid 查找 git 项目的功能
"""

import os
from pathlib import Path
from typing import Optional, List, Tuple


def find_git_root(start: Path) -> Optional[Path]:
    """
    向上查找 git 根目录

    Args:
        start: 起始目录

    Returns:
        git 根目录路径，如果未找到则返回 None
    """
    current = start
    while current:
        if (current / '.git').exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def find_repo_by_appid(search_root: Path, appid: str) -> Path:
    """
    在指定目录下查找包含指定 appid 的 git 项目

    Args:
        search_root: 搜索根目录
        appid: 应用 ID

    Returns:
        找到的 git 仓库根目录

    Raises:
        Exception: 未找到项目或找到多个项目
    """
    print(f"正在查找 appid={appid} 的项目...")

    matches: List[Tuple[Path, Path]] = []

    for root, dirs, files in os.walk(search_root):
        # 跳过 .git 目录
        if '.git' in dirs:
            dirs.remove('.git')

        if 'app.properties' in files:
            props_file = Path(root) / 'app.properties'
            try:
                with open(props_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('app.id='):
                            found_appid = line.split('=', 1)[1].strip()
                            if found_appid == appid:
                                # 查找 git 根目录
                                git_root = find_git_root(Path(root))
                                if git_root:
                                    matches.append((props_file, git_root))
            except Exception:
                continue

    if not matches:
        raise Exception(f"在 {search_root} 下未找到 app.id={appid} 的项目")

    # 检查是否有多个不同的 repo root
    first_root = matches[0][1]
    if not all(root == first_root for _, root in matches):
        msg = f"发现多个 app.id={appid} 的候选仓库:\n"
        for props_file, repo_root in matches:
            msg += f"- {repo_root} ({props_file})\n"
        raise Exception(msg)

    return first_root


def read_app_properties(props_file: Path) -> dict:
    """
    读取 app.properties 文件内容

    Args:
        props_file: app.properties 文件路径

    Returns:
        包含配置项的字典
    """
    properties = {}
    try:
        with open(props_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        properties[key.strip()] = value.strip()
    except Exception as e:
        raise Exception(f"读取 {props_file} 失败: {e}")

    return properties

"""
仓库查找模块
提供根据 appid 查找 git 项目的功能，以及直接使用本地路径或 git URL 的功能
"""

import os
import subprocess
import tempfile
import shutil
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


def is_git_url(repo: str) -> bool:
    """
    判断字符串是否是 git URL

    Args:
        repo: 仓库字符串

    Returns:
        是否是 git URL
    """
    git_url_patterns = [
        'git@',
        'https://',
        'http://',
        'ssh://',
        'git://',
    ]
    return any(repo.startswith(pattern) for pattern in git_url_patterns)


def clone_git_repo(git_url: str, target_dir: Optional[Path] = None) -> Path:
    """
    克隆 git 仓库到指定目录

    Args:
        git_url: git 仓库 URL
        target_dir: 目标目录（如果为 None，则使用临时目录）

    Returns:
        克隆后的仓库根目录

    Raises:
        Exception: 克隆失败
    """
    if target_dir is None:
        target_dir = Path(tempfile.mkdtemp(prefix='git-clone-'))
    else:
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

    print(f"正在克隆仓库: {git_url}")
    print(f"目标目录: {target_dir}")

    try:
        result = subprocess.run(
            ['git', 'clone', git_url, str(target_dir)],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ 克隆成功")
        return target_dir
    except subprocess.CalledProcessError as e:
        raise Exception(f"克隆仓库失败: {e.stderr}")


def resolve_repo(repo: str, clone_dir: Optional[Path] = None) -> Path:
    """
    解析仓库参数，支持本地路径和 git URL

    Args:
        repo: 仓库参数，可以是：
            - 本地路径（相对或绝对）
            - git URL（git@github.com:user/repo.git, https://github.com/user/repo.git 等）
        clone_dir: 如果是 git URL，克隆到的目标目录（可选，默认使用临时目录）

    Returns:
        仓库根目录路径

    Raises:
        Exception: 无效的仓库路径或克隆失败
    """
    # 判断是否是 git URL
    if is_git_url(repo):
        return clone_git_repo(repo, clone_dir)

    # 作为本地路径处理
    repo_path = Path(repo).expanduser().resolve()

    if not repo_path.exists():
        raise Exception(f"路径不存在: {repo_path}")

    if not repo_path.is_dir():
        raise Exception(f"路径不是目录: {repo_path}")

    # 查找 git 根目录
    git_root = find_git_root(repo_path)
    if git_root is None:
        raise Exception(f"路径不在 git 仓库中: {repo_path}")

    print(f"找到本地仓库: {git_root}")
    return git_root

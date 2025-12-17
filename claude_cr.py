#!/usr/bin/env python3
"""
Claude Code Review Tool - Python 版本

支持三种模式：
1. review - 代码审查（默认）
2. analyze - 代码变更解析
3. priority - Review 优先级评估
"""

import sys
import subprocess
import argparse
import threading
import itertools
import time
from pathlib import Path

# 导入自定义模块
from repo_finder import find_repo_by_appid, resolve_repo
from git_utils import resolve_branch_comparison, get_name_status, get_diff
from json_utils import extract_json_from_text, validate_review_schema, create_fallback_review, format_json
from prompt_utils import (
    build_full_prompt,
    build_change_analysis_prompt,
    build_review_priority_prompt,
    save_prompt_to_file
)
from generate_report import (
    load_json_file,
    detect_report_type,
    generate_review_report,
    generate_analyze_report,
    generate_priority_report,
    generate_combined_report
)


def run_claude_analysis(prompt: str, output_dir: Path = None, mode: str = "review", repo_root: Path = None, with_context: bool = False) -> str:
    """
    调用 Claude CLI 进行分析，并确保输出符合 schema

    Args:
        prompt: 分析 prompt
        output_dir: 输出目录（可选）
        mode: 模式（review/analyze/priority）
        repo_root: 仓库根目录（可选，用于 with_context 模式）
        with_context: 是否启用仓库上下文访问（在仓库目录下运行 Claude）

    Returns:
        格式化的 JSON 结果

    Raises:
        Exception: Claude CLI 调用失败
    """
    mode_names = {
        "review": "Code Review",
        "analyze": "代码变更解析",
        "priority": "Review 优先级评估"
    }

    if with_context and repo_root:
        print(f"✓ 启用仓库上下文访问模式")
        print(f"✓ 工作目录: {repo_root}")
        print(f"✓ Claude 可以使用 Read、Grep、Glob 等工具访问仓库代码\n")
    else:
        print("")

    # 检查 claude 命令是否存在
    result = subprocess.run(['which', 'claude'], capture_output=True)
    if result.returncode != 0:
        raise Exception(
            "未找到 claude 命令，请确保已安装 Claude Code。\n"
            "安装方法: npm install -g @anthropic-ai/claude-code"
        )

    # 准备 subprocess 参数
    run_kwargs = {
        'input': prompt,
        'capture_output': True,
        'text': True
    }

    # 如果启用 with_context，在仓库目录下运行
    if with_context and repo_root:
        run_kwargs['cwd'] = str(repo_root)

    # Loading 动画设置
    loading = True
    spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])

    def show_loading():
        """显示 loading 动画"""
        while loading:
            sys.stdout.write(f'\r正在生成 [{mode_names.get(mode, mode)}] 报告 {next(spinner)} ')
            sys.stdout.flush()
            time.sleep(0.1)

    # 启动 loading 动画线程
    loading_thread = threading.Thread(target=show_loading, daemon=True)
    loading_thread.start()

    try:
        # 调用 claude
        result = subprocess.run(
            ['claude', '-p', '-'],
            **run_kwargs
        )

        if result.returncode != 0:
            raise Exception(f"claude 命令执行失败:\n{result.stderr}")

        raw_output = result.stdout
    finally:
        # 停止 loading 动画
        loading = False
        loading_thread.join(timeout=1)
        # 清除 loading 行并显示完成信息
        sys.stdout.write('\r' + ' ' * 80 + '\r')
        sys.stdout.flush()
        print(f"✓ [{mode_names.get(mode, mode)}] 报告生成完成\n")

    # 保存原始输出（用于调试）
    if output_dir:
        raw_output_file = output_dir / 'raw_output.txt'
        with open(raw_output_file, 'w', encoding='utf-8') as f:
            f.write(raw_output)

    # 尝试提取 JSON
    print("正在验证输出格式...")
    json_data = extract_json_from_text(raw_output)

    if json_data is None:
        print("警告: 无法从输出中提取有效的 JSON")
        print(f"原始输出长度: {len(raw_output)} 字符")
        print(f"原始输出前 500 字符: {raw_output[:500]}")
        print("将使用后备方案...")

        # 只有 review 模式才使用后备方案
        if mode == "review":
            fallback = create_fallback_review("无法提取 JSON")
            return format_json(fallback)
        else:
            # 其他模式直接返回原始输出
            return raw_output

    # 只有 review 模式才验证 schema
    if mode == "review" and not validate_review_schema(json_data):
        print("警告: 输出不符合预期的 schema")
        print("将使用后备方案...")
        fallback = create_fallback_review("Schema 验证失败")
        return format_json(fallback)

    print("✓ 输出格式验证通过")

    # 返回格式化的 JSON
    return format_json(json_data)


def generate_html_report(json_file: Path, mode: str) -> Path:
    """
    根据 JSON 结果生成 HTML 报告

    Args:
        json_file: JSON 结果文件路径
        mode: 模式（review/analyze/priority）

    Returns:
        生成的 HTML 文件路径
    """
    try:
        # 加载 JSON 数据
        data = load_json_file(str(json_file))

        # 根据模式生成对应的 HTML
        if mode == 'review':
            html = generate_review_report(data)
        elif mode == 'analyze':
            html = generate_analyze_report(data)
        elif mode == 'priority':
            html = generate_priority_report(data)
        else:
            print(f"警告: 未知模式 {mode}，跳过 HTML 生成")
            return None

        # 保存 HTML 文件
        html_file = json_file.with_suffix('.html')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)

        return html_file

    except Exception as e:
        print(f"警告: 生成 HTML 报告失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Claude Code Review Tool - 支持代码审查、变更解析、优先级评估',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
模式说明：
  all      - 完整分析（默认）：同时运行 analyze、priority 和 review 三种分析
  review   - 代码审查：识别代码问题和改进建议
  analyze  - 代码变更解析：理解变更目的、影响范围和架构影响
  priority - Review 优先级评估：识别最需要 review 的代码部分和预估时长

示例：
  # 使用本地仓库路径
  %(prog)s --repo /path/to/repo -b main -t feature/test

  # 使用当前目录
  %(prog)s --repo . -b main -t feature/test

  # 使用 git URL（会自动克隆到临时目录）
  %(prog)s --repo https://github.com/user/repo.git -b main -t feature/test

  # 完整分析（同时运行三种模式）
  %(prog)s --repo /path/to/repo -b main -t feature/test

  # 仅代码审查
  %(prog)s --repo /path/to/repo -b main -t feature/test --mode review

  # 代码变更解析
  %(prog)s --repo /path/to/repo -b main -t feature/test --mode analyze

  # Review 优先级评估
  %(prog)s --repo /path/to/repo -b main -t feature/test --mode priority
        """
    )
    parser.add_argument('--repo', '-r', help='仓库路径或 git URL（本地路径、git@github.com:user/repo.git、https://github.com/user/repo.git 等）')
    parser.add_argument('--appid', '-a', help='[已弃用] 应用 ID（请使用 --repo 参数）')
    parser.add_argument('--basebranch', '-b', required=True, help='Base branch name')
    parser.add_argument('--targetbranch', '-t', required=True, help='Target branch name')
    parser.add_argument('--search-root', '-s', default='~/VibeCoding/apprepo', help='[仅在使用 --appid 时有效] 搜索根目录')
    parser.add_argument('--clone-dir', help='[仅在使用 git URL 时有效] 克隆目录（默认使用临时目录）')
    parser.add_argument('--mode', '-m',
                       choices=['all', 'review', 'analyze', 'priority'],
                       default='all',
                       help='运行模式：all(完整分析), review(代码审查), analyze(变更解析), priority(优先级评估)')
    parser.add_argument('--prompt-only', action='store_true',
                       help='只生成 prompt，不调用 Claude')
    parser.add_argument('--no-context', action='store_true',
                       help='禁用仓库上下文访问（默认启用）：不在仓库目录下运行 Claude')

    args = parser.parse_args()

    # 参数验证：必须提供 --repo 或 --appid 之一
    if not args.repo and not args.appid:
        parser.error('必须提供 --repo 或 --appid 参数之一')

    # 如果同时提供了两个参数，警告并优先使用 --repo
    if args.repo and args.appid:
        print('警告: 同时提供了 --repo 和 --appid，将使用 --repo 参数')
        print('')

    # 默认启用仓库上下文访问，除非指定 --no-context
    with_context = not args.no_context

    try:
        # 1. 获取仓库路径
        if args.repo:
            # 使用新的 resolve_repo 函数
            clone_dir = Path(args.clone_dir) if args.clone_dir else None
            repo_root = resolve_repo(args.repo, clone_dir)
            repo_identifier = args.repo  # 用于文件命名
        else:
            # 向后兼容：使用旧的 appid 查找方式
            print('警告: --appid 参数已弃用，建议使用 --repo 参数')
            print('')
            search_root = Path(args.search_root).expanduser()
            if not search_root.exists():
                print(f"搜索目录不存在，正在创建: {search_root}")
                search_root.mkdir(parents=True, exist_ok=True)
            repo_root = find_repo_by_appid(search_root, args.appid)
            repo_identifier = args.appid  # 用于文件命名

        print(f"找到项目: {repo_root}")

        # 2. 获取 git diff 信息
        comparison = resolve_branch_comparison(repo_root, args.basebranch, args.targetbranch)
        name_status = get_name_status(repo_root, comparison)
        diff = get_diff(repo_root, comparison)

        # 3. 确定要运行的模式列表
        if args.mode == 'all':
            modes_to_run = ['analyze', 'priority', 'review']
        else:
            modes_to_run = [args.mode]

        # 4. 为每个模式构建 prompt 并运行
        output_dir = None
        for mode in modes_to_run:
            if mode == 'review':
                prompt = build_full_prompt(
                    repo_identifier, args.basebranch, args.targetbranch,
                    repo_root, comparison, name_status, diff, with_context
                )
                result_filename = 'review_result.json'
            elif mode == 'analyze':
                prompt = build_change_analysis_prompt(
                    repo_identifier, args.basebranch, args.targetbranch,
                    repo_root, comparison, name_status, diff, with_context
                )
                result_filename = 'change_analysis.json'
            elif mode == 'priority':
                prompt = build_review_priority_prompt(
                    repo_identifier, args.basebranch, args.targetbranch,
                    repo_root, comparison, name_status, diff, with_context
                )
                result_filename = 'review_priority.json'
            else:
                raise Exception(f"不支持的模式: {mode}")

            # 保存 prompt 到文件
            if output_dir is None:
                output_dir = save_prompt_to_file(prompt, repo_identifier, args.basebranch, args.targetbranch, repo_root, mode)
                print(f"输出目录: {output_dir}")
            else:
                # 保存额外的 prompt 文件
                prompt_file = output_dir / f'prompt_{mode}.txt'
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(prompt)

            if args.prompt_only:
                print(f"[{mode}] Prompt 已生成")
                continue

            # 调用 Claude CLI
            print(f"\n{'='*50}")
            print(f"运行模式: {mode}")
            if with_context:
                print(f"仓库上下文: 已启用（工作目录: {repo_root}）")
            print(f"{'='*50}")
            result = run_claude_analysis(prompt, output_dir, mode, repo_root, with_context)

            # 保存结果
            result_file = output_dir / result_filename
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"JSON 结果已保存到: {result_file}")

            # 自动生成 HTML 报告
            html_file = generate_html_report(result_file, mode)
            if html_file:
                print(f"HTML 报告已生成: {html_file}\n")
            else:
                print("")

            print(result)

        if args.prompt_only:
            print(f"\n可以查看生成的 prompt 文件: {output_dir}")
        else:
            # 如果是 all 模式，生成合并报告
            if args.mode == 'all':
                print(f"\n{'='*50}")
                print("正在生成综合报告...")
                print(f"{'='*50}")

                # 加载各个 JSON 结果
                analyze_data = None
                priority_data = None
                review_data = None

                analyze_file = output_dir / 'change_analysis.json'
                priority_file = output_dir / 'review_priority.json'
                review_file = output_dir / 'review_result.json'

                if analyze_file.exists():
                    try:
                        analyze_data = load_json_file(str(analyze_file))
                    except Exception:
                        pass

                if priority_file.exists():
                    try:
                        priority_data = load_json_file(str(priority_file))
                    except Exception:
                        pass

                if review_file.exists():
                    try:
                        review_data = load_json_file(str(review_file))
                    except Exception:
                        pass

                # 生成合并报告
                combined_html = generate_combined_report(analyze_data, priority_data, review_data)
                combined_file = output_dir / 'report.html'
                with open(combined_file, 'w', encoding='utf-8') as f:
                    f.write(combined_html)
                print(f"综合报告已生成: {combined_file}")

            # 输出所有生成的报告文件
            print(f"\n{'='*50}")
            print("所有报告已生成完毕")
            print(f"{'='*50}")
            print(f"输出目录: {output_dir}")

            if args.mode == 'all':
                print("\n推荐打开综合报告（支持 Tab 切换）:")
                print(f"  open \"{output_dir / 'report.html'}\"")
                print("\n或分别查看各报告:")
            else:
                print("\n可以在浏览器中打开 HTML 报告:")

            for mode in modes_to_run:
                if mode == 'review':
                    html_name = 'review_result.html'
                elif mode == 'analyze':
                    html_name = 'change_analysis.html'
                elif mode == 'priority':
                    html_name = 'review_priority.html'
                html_path = output_dir / html_name
                if html_path.exists():
                    print(f"  open \"{html_path}\"")

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

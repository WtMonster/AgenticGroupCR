#!/usr/bin/env python3
"""
Copilot Code Review Tool - 使用 GitHub Copilot CLI 进行 code review

支持三种模式（与 claude_cr.py / codex_cr.py 对齐）：
1. review - 代码审查（默认）
2. analyze - 代码变更解析
3. priority - Review 优先级评估
"""

import sys
import subprocess
import argparse
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple, Any

# 导入通用模块（与 claude_cr.py / codex_cr.py 共享）
from repo_finder import find_repo_by_appid
from git_utils import resolve_branch_comparison, get_name_status, get_diff, update_repo
from json_utils import extract_json_from_text, validate_review_schema, create_fallback_review, format_json
from prompt_utils import (
    build_full_prompt,
    build_change_analysis_prompt,
    build_review_priority_prompt,
    save_prompt_to_file
)
from generate_report import (
    generate_review_report,
    generate_analyze_report,
    generate_priority_report,
    generate_combined_report,
    load_json_file
)


# Copilot 支持的模型
COPILOT_MODELS = {
    # Claude 系列
    'claude-sonnet-4.5': 'claude-sonnet-4.5',
    'claude-haiku-4.5': 'claude-haiku-4.5',
    'claude-opus-4.5': 'claude-opus-4.5',
    'claude-sonnet-4': 'claude-sonnet-4',
    # GPT 系列
    'gpt-5.1-codex-max': 'gpt-5.1-codex-max',
    'gpt-5.1-codex': 'gpt-5.1-codex',
    'gpt-5.2': 'gpt-5.2',
    'gpt-5.1': 'gpt-5.1',
    'gpt-5': 'gpt-5',
    'gpt-5.1-codex-mini': 'gpt-5.1-codex-mini',
    'gpt-5-mini': 'gpt-5-mini',
    'gpt-4.1': 'gpt-4.1',
    # Gemini 系列
    'gemini-3-pro-preview': 'gemini-3-pro-preview',
    # 简写别名
    'sonnet': 'claude-sonnet-4.5',
    'haiku': 'claude-haiku-4.5',
    'opus': 'claude-opus-4.5',
    'codex-max': 'gpt-5.1-codex-max',
    'codex': 'gpt-5.1-codex',
    'gemini': 'gemini-3-pro-preview',
}


def run_copilot_with_prompt(
    prompt: str,
    repo_root: Path,
    output_dir: Path = None,
    mode: str = "review",
    model: str = None
) -> str:
    """
    使用自定义 prompt 调用 copilot -p

    使用 -p 参数进行非交互式执行，-s 参数只输出 agent 响应。
    使用 --allow-all-tools 允许所有工具自动执行。

    Args:
        prompt: 自定义 prompt
        repo_root: 仓库根目录
        output_dir: 输出目录
        mode: 模式（review/analyze/priority）
        model: 指定使用的模型

    Returns:
        Copilot 的输出结果

    Raises:
        Exception: copilot 命令执行失败
    """
    mode_names = {
        "review": "code review",
        "analyze": "代码变更解析",
        "priority": "review 优先级评估"
    }
    print(f"正在调用 Copilot 进行 {mode_names.get(mode, mode)}...")
    print(f"仓库目录: {repo_root}")

    # 检查 copilot 命令是否存在
    result = subprocess.run(['which', 'copilot'], capture_output=True)
    if result.returncode != 0:
        raise Exception(
            "未找到 copilot 命令，请确保已安装 GitHub Copilot CLI。\n"
            "安装方法: 在 VS Code 中安装 GitHub Copilot Chat 扩展"
        )

    # 构建 copilot 命令
    # -p: 非交互式执行 prompt
    # -s: silent 模式，只输出 agent 响应
    # --allow-all-tools: 允许所有工具自动执行
    cmd = ['copilot', '-p', prompt, '-s', '--allow-all-tools']

    # 添加模型参数
    if model:
        # 处理模型别名
        actual_model = COPILOT_MODELS.get(model, model)
        cmd.extend(['--model', actual_model])
        print(f"使用模型: {actual_model}")

    print(f"执行命令: copilot -p <prompt> -s --allow-all-tools" + (f" --model {COPILOT_MODELS.get(model, model)}" if model else ""))
    print(f"Prompt 长度: {len(prompt)} 字符\n")

    # 在仓库目录下执行 copilot
    result = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True
    )

    # 打印 stderr（copilot 的进度信息）
    if result.stderr:
        print("Copilot 进度信息:")
        print(result.stderr)

    if result.returncode != 0:
        print(f"copilot 命令执行失败:")
        print(f"stderr: {result.stderr}")
        raise Exception(f"copilot 执行失败，退出码: {result.returncode}")

    # stdout 是 agent 的响应
    raw_output = result.stdout

    if output_dir:
        # 保存到 raw_output.txt
        raw_output_file = output_dir / 'raw_output.txt'
        with open(raw_output_file, 'a', encoding='utf-8') as f:
            f.write(f"\n\n{'='*50}\n")
            f.write(f"Mode: {mode}\n")
            f.write(f"{'='*50}\n\n")
            f.write(raw_output)
        print(f"✓ 原始输出已保存到: {raw_output_file}")

    return raw_output


def generate_html_report(json_file: Path, mode: str) -> Path:
    """
    根据 JSON 结果生成 HTML 报告（复用 generate_report 模块）

    Args:
        json_file: JSON 结果文件路径
        mode: 模式（review/analyze/priority）

    Returns:
        生成的 HTML 文件路径
    """
    try:
        data = load_json_file(str(json_file))

        if mode == 'review':
            html = generate_review_report(data)
        elif mode == 'analyze':
            html = generate_analyze_report(data)
        elif mode == 'priority':
            html = generate_priority_report(data)
        else:
            print(f"警告: 未知模式 {mode}，跳过 HTML 生成")
            return None

        html_file = json_file.with_suffix('.html')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)

        return html_file

    except Exception as e:
        print(f"警告: 生成 HTML 报告失败: {e}")
        return None


# 线程安全的打印锁
print_lock = threading.Lock()


def thread_safe_print(*args, **kwargs):
    """线程安全的打印函数"""
    with print_lock:
        print(*args, **kwargs)


def save_meta_info(
    output_dir: Path,
    appid: str,
    base_branch: str,
    target_branch: str,
    repo_root: Path,
    comparison: dict = None,
    mode: str = "review",
    model: str = None
) -> None:
    """
    保存元信息到文件
    """
    meta_file = output_dir / 'meta.txt'
    with open(meta_file, 'w', encoding='utf-8') as f:
        f.write(f"Tool: Copilot\n")
        f.write(f"Mode: {mode}\n")
        if model:
            actual_model = COPILOT_MODELS.get(model, model)
            f.write(f"Model: {actual_model}\n")
        f.write(f"AppID: {appid}\n")
        f.write(f"Repo Root: {repo_root}\n")
        f.write(f"Base Branch: {base_branch}\n")
        f.write(f"Target Branch: {target_branch}\n")
        if comparison:
            f.write(f"Base SHA: {comparison.get('base_sha', 'N/A')}\n")
            f.write(f"Target SHA: {comparison.get('target_sha', 'N/A')}\n")
            f.write(f"Merge Base SHA: {comparison.get('merge_base_sha', 'N/A')}\n")
        f.write(f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


def run_single_mode_analysis(
    mode: str,
    prompt: str,
    output_dir: Path,
    repo_root: Path,
    result_filename: str,
    model: str = None
) -> Tuple[str, str, bool, str]:
    """
    运行单个模式的分析（用于并行执行）

    Args:
        mode: 模式（review/analyze/priority）
        prompt: 分析 prompt
        output_dir: 输出目录
        repo_root: 仓库根目录
        result_filename: 结果文件名
        model: 指定使用的模型

    Returns:
        (mode, result_filename, success, result_or_error)
    """
    try:
        thread_safe_print(f"\n[{mode}] 开始分析...")

        # 调用 Copilot
        raw_output = run_copilot_with_prompt(
            prompt, repo_root, output_dir, mode,
            model=model
        )

        # 提取 JSON
        json_data = extract_json_from_text(raw_output, mode)

        if json_data is None:
            thread_safe_print(f"[{mode}] 警告: 无法从输出中提取有效的 JSON")
            if mode == "review":
                fallback = create_fallback_review("无法提取 JSON")
                result = format_json(fallback)
            else:
                result = raw_output
        elif mode == "review" and not validate_review_schema(json_data):
            thread_safe_print(f"[{mode}] 警告: 输出不符合预期的 schema")
            fallback = create_fallback_review("Schema 验证失败")
            result = format_json(fallback)
        else:
            thread_safe_print(f"[{mode}] ✓ 输出格式验证通过")
            result = format_json(json_data)

        # 保存结果
        result_file = output_dir / result_filename
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(result)
        thread_safe_print(f"[{mode}] ✓ JSON 结果已保存到: {result_file}")

        # 生成 HTML 报告
        html_file = generate_html_report(result_file, mode)
        if html_file:
            thread_safe_print(f"[{mode}] ✓ HTML 报告已生成: {html_file}")

        thread_safe_print(f"[{mode}] ✓ 分析完成")
        return (mode, result_filename, True, result)

    except Exception as e:
        thread_safe_print(f"[{mode}] ✗ 分析失败: {e}")
        return (mode, result_filename, False, str(e))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Copilot Code Review Tool - 支持代码审查、变更解析、优先级评估',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
模式说明（与 claude_cr.py / codex_cr.py 完全对齐）：
  all      - 完整分析（默认）：同时运行 analyze、priority 和 review 三种分析
  review   - 代码审查：识别代码问题和改进建议
  analyze  - 代码变更解析：理解变更目的、影响范围和架构影响
  priority - Review 优先级评估：识别最需要 review 的代码部分和预估时长

可用模型：
  Claude 系列: claude-sonnet-4.5, claude-haiku-4.5, claude-opus-4.5, claude-sonnet-4
  GPT 系列: gpt-5.1-codex-max, gpt-5.1-codex, gpt-5.2, gpt-5.1, gpt-5, gpt-5-mini, gpt-4.1
  Gemini 系列: gemini-3-pro-preview
  简写别名: sonnet, haiku, opus, codex-max, codex, gemini

示例：
  # 完整分析（同时运行三种模式）
  %(prog)s -a 100027304 -b main -t feature/test

  # 使用 Claude Sonnet 模型
  %(prog)s -a 100027304 -b main -t feature/test -M sonnet

  # 使用 GPT-5.1 Codex Max 模型
  %(prog)s -a 100027304 -b main -t feature/test -M codex-max

  # 仅代码审查
  %(prog)s -a 100027304 -b main -t feature/test --mode review

  # 代码变更解析
  %(prog)s -a 100027304 -b main -t feature/test --mode analyze

  # Review 优先级评估
  %(prog)s -a 100027304 -b main -t feature/test --mode priority
        """
    )
    parser.add_argument('--appid', '-a', required=True, help='Application ID')
    parser.add_argument('--basebranch', '-b', required=True, help='Base branch name')
    parser.add_argument('--targetbranch', '-t', required=True, help='Target branch name')
    parser.add_argument('--search-root', '-s', default='~/VibeCoding/apprepo', help='Search root directory')
    parser.add_argument('--mode', '-m',
                       choices=['all', 'review', 'analyze', 'priority'],
                       default='all',
                       help='运行模式：all(完整分析), review(代码审查), analyze(变更解析), priority(优先级评估)')
    parser.add_argument('--prompt-only', action='store_true',
                       help='只生成 prompt，不调用 Copilot')
    parser.add_argument('--no-context', action='store_true',
                       help='禁用仓库上下文访问（默认启用）')
    parser.add_argument('--model', '-M',
                       default=None,
                       help='指定 Copilot 使用的模型（如 sonnet, opus, gpt-5.1, codex-max 等）')
    parser.add_argument('--no-update', action='store_true',
                       help='跳过仓库更新（默认会自动 fetch 并更新分支）')

    args = parser.parse_args()

    # 默认启用仓库上下文访问
    with_context = not args.no_context

    try:
        # 1. 查找 git 项目（复用 repo_finder）
        search_root = Path(args.search_root).expanduser()
        if not search_root.exists():
            print(f"搜索目录不存在，正在创建: {search_root}")
            search_root.mkdir(parents=True, exist_ok=True)

        repo_root = find_repo_by_appid(search_root, args.appid)
        print(f"找到项目: {repo_root}")

        # 2. 更新仓库（默认启用，除非指定 --no-update）
        if not args.no_update:
            update_repo(repo_root, args.basebranch, args.targetbranch)

        # 3. 获取 git diff 信息（复用 git_utils）
        comparison = resolve_branch_comparison(repo_root, args.basebranch, args.targetbranch)
        name_status = get_name_status(repo_root, comparison)
        diff = get_diff(repo_root, comparison)

        # 3. 确定要运行的模式列表
        if args.mode == 'all':
            modes_to_run = ['analyze', 'priority', 'review']
        else:
            modes_to_run = [args.mode]

        # 4. 构建所有模式的 prompt
        mode_configs = {}
        for mode in modes_to_run:
            if mode == 'review':
                prompt = build_full_prompt(
                    args.appid, args.basebranch, args.targetbranch,
                    repo_root, comparison, name_status, diff, with_context
                )
                result_filename = 'review_result.json'
            elif mode == 'analyze':
                prompt = build_change_analysis_prompt(
                    args.appid, args.basebranch, args.targetbranch,
                    repo_root, comparison, name_status, diff, with_context
                )
                result_filename = 'change_analysis.json'
            elif mode == 'priority':
                prompt = build_review_priority_prompt(
                    args.appid, args.basebranch, args.targetbranch,
                    repo_root, comparison, name_status, diff, with_context
                )
                result_filename = 'review_priority.json'
            else:
                raise Exception(f"不支持的模式: {mode}")

            mode_configs[mode] = {
                'prompt': prompt,
                'result_filename': result_filename
            }

        # 5. 创建输出目录并保存所有 prompt
        first_mode = modes_to_run[0]
        output_dir = save_prompt_to_file(
            mode_configs[first_mode]['prompt'],
            args.appid, args.basebranch, args.targetbranch, repo_root, first_mode
        )
        # 修改目录名前缀为 copilot-review
        old_dir = output_dir
        new_dir_name = output_dir.name.replace('review-prompt-', 'copilot-review-')
        output_dir = output_dir.parent / new_dir_name
        old_dir.rename(output_dir)
        print(f"输出目录: {output_dir}")

        # 保存元信息
        save_meta_info(
            output_dir, args.appid, args.basebranch, args.targetbranch, repo_root, comparison, args.mode,
            model=args.model
        )

        # 保存其他模式的 prompt 文件
        for mode in modes_to_run[1:]:
            prompt_file = output_dir / f'prompt_{mode}.txt'
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(mode_configs[mode]['prompt'])

        if args.prompt_only:
            for mode in modes_to_run:
                print(f"[{mode}] Prompt 已生成")
        else:
            # 6. 并行执行所有模式的分析
            print(f"\n{'='*50}")
            if len(modes_to_run) > 1:
                print(f"并行运行 {len(modes_to_run)} 个模式: {', '.join(modes_to_run)} (Copilot)")
            else:
                print(f"运行模式: {modes_to_run[0]} (Copilot)")
            if with_context:
                print(f"仓库上下文: 已启用（工作目录: {repo_root}）")
            print(f"{'='*50}")

            results = {}

            if len(modes_to_run) == 1:
                # 单模式：串行执行
                mode = modes_to_run[0]
                config = mode_configs[mode]
                mode_result = run_single_mode_analysis(
                    mode, config['prompt'], output_dir, repo_root, config['result_filename'],
                    model=args.model
                )
                results[mode] = mode_result
            else:
                # 多模式：并行执行
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {}
                    for mode in modes_to_run:
                        config = mode_configs[mode]
                        future = executor.submit(
                            run_single_mode_analysis,
                            mode, config['prompt'], output_dir, repo_root, config['result_filename'],
                            args.model
                        )
                        futures[future] = mode

                    # 等待所有任务完成
                    for future in as_completed(futures):
                        mode = futures[future]
                        try:
                            mode_result = future.result()
                            results[mode] = mode_result
                        except Exception as e:
                            print(f"[{mode}] 执行异常: {e}")
                            results[mode] = (mode, mode_configs[mode]['result_filename'], False, str(e))

            # 打印执行结果摘要
            print(f"\n{'='*50}")
            print("执行结果摘要:")
            print(f"{'='*50}")
            for mode in modes_to_run:
                if mode in results:
                    _, _, success, _ = results[mode]
                    status = "✓ 成功" if success else "✗ 失败"
                    print(f"  [{mode}] {status}")

        if args.prompt_only:
            print(f"\n可以查看生成的 prompt 文件: {output_dir}")
        else:
            # 如果是 all 模式，生成合并报告（复用 generate_report）
            if args.mode == 'all':
                print(f"\n{'='*50}")
                print("正在生成综合报告...")
                print(f"{'='*50}")

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

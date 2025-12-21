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
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

# 导入自定义模块
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
        "review": "code review",
        "analyze": "代码变更解析",
        "priority": "review 优先级评估"
    }
    print(f"正在调用 Claude CLI 进行 {mode_names.get(mode, mode)}...")

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

    # 调用 claude
    result = subprocess.run(
        ['claude', '-p', '-'],
        **run_kwargs
    )

    if result.returncode != 0:
        raise Exception(f"claude 命令执行失败:\n{result.stderr}")

    raw_output = result.stdout

    # 保存原始输出（用于调试）
    if output_dir:
        raw_output_file = output_dir / 'raw_output.txt'
        with open(raw_output_file, 'w', encoding='utf-8') as f:
            f.write(raw_output)

    # 尝试提取 JSON（传入 mode 参数以支持不同格式的 JSON 提取）
    print("正在验证输出格式...")
    json_data = extract_json_from_text(raw_output, mode)

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


def generate_html_report(json_file: Path, mode: str, diff_content: str = None) -> Path:
    """
    根据 JSON 结果生成 HTML 报告

    Args:
        json_file: JSON 结果文件路径
        mode: 模式（review/analyze/priority）
        diff_content: git diff 输出内容，用于展示代码变更

    Returns:
        生成的 HTML 文件路径
    """
    try:
        # 加载 JSON 数据
        data = load_json_file(str(json_file))

        # 根据模式生成对应的 HTML
        if mode == 'review':
            html = generate_review_report(data, diff_content)
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


# 线程安全的打印锁

# 定义各模式的 JSON Schema，用于 --json-schema 参数强制输出格式
JSON_SCHEMAS = {
    'review': {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "confidence_score": {"type": "number"},
                        "priority": {"type": "integer"},
                        "code_location": {
                            "type": "object",
                            "properties": {
                                "absolute_file_path": {"type": "string"},
                                "line_range": {
                                    "type": "object",
                                    "properties": {
                                        "start": {"type": "integer"},
                                        "end": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    },
                    "required": ["title", "body", "priority"]
                }
            },
            "overall_correctness": {"type": "string"},
            "overall_explanation": {"type": "string"},
            "overall_confidence_score": {"type": "number"}
        },
        "required": ["findings", "overall_correctness"]
    },
    'analyze': {
        "type": "object",
        "properties": {
            "change_summary": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "purpose": {"type": "string"},
                    "scope": {"type": "string"},
                    "type": {"type": "string"},
                    "risk_level": {"type": "string"},
                    "estimated_complexity": {"type": "string"}
                },
                "required": ["title", "purpose"]
            },
            "file_changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "change_type": {"type": "string"},
                        "purpose": {"type": "string"},
                        "key_changes": {"type": "array", "items": {"type": "string"}},
                        "impact": {"type": "string"}
                    }
                }
            },
            "architecture_impact": {"type": "object"},
            "migration_notes": {"type": "array", "items": {"type": "string"}},
            "confidence_score": {"type": "number"}
        },
        "required": ["change_summary", "file_changes"]
    },
    'priority': {
        "type": "object",
        "properties": {
            "review_summary": {
                "type": "object",
                "properties": {
                    "total_files": {"type": "integer"},
                    "high_priority_files": {"type": "integer"},
                    "medium_priority_files": {"type": "integer"},
                    "low_priority_files": {"type": "integer"},
                    "estimated_total_minutes": {"type": "integer"},
                    "recommended_reviewers": {"type": "integer"},
                    "complexity_score": {"type": "number"}
                }
            },
            "priority_areas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "priority": {"type": "string"},
                        "file_path": {"type": "string"},
                        "reason": {"type": "string"},
                        "focus_points": {"type": "array", "items": {"type": "string"}},
                        "estimated_minutes": {"type": "integer"}
                    }
                }
            },
            "file_priorities": {"type": "array"},
            "review_strategy": {"type": "object"},
            "time_breakdown": {"type": "object"},
            "confidence_score": {"type": "number"}
        },
        "required": ["review_summary", "priority_areas"]
    }
}

print_lock = threading.Lock()


def thread_safe_print(*args, **kwargs):
    """线程安全的打印函数"""
    with print_lock:
        print(*args, **kwargs)


def format_tool_call_detail(tool_name: str, tool_input: dict) -> str:
    """
    格式化工具调用详情，展示关键参数

    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数

    Returns:
        格式化的工具调用描述
    """
    # 根据不同工具类型提取关键信息
    if tool_name == 'Read':
        file_path = tool_input.get('file_path', '')
        # 只显示文件名，不显示完整路径
        filename = file_path.split('/')[-1] if file_path else 'unknown'
        return f"Read: {filename}"

    elif tool_name == 'Grep':
        pattern = tool_input.get('pattern', '')
        path = tool_input.get('path', '.')
        return f"Grep: '{pattern}' in {path}"

    elif tool_name == 'Glob':
        pattern = tool_input.get('pattern', '')
        return f"Glob: {pattern}"

    elif tool_name == 'Edit':
        file_path = tool_input.get('file_path', '')
        filename = file_path.split('/')[-1] if file_path else 'unknown'
        return f"Edit: {filename}"

    elif tool_name == 'Write':
        file_path = tool_input.get('file_path', '')
        filename = file_path.split('/')[-1] if file_path else 'unknown'
        return f"Write: {filename}"

    elif tool_name == 'Bash':
        command = tool_input.get('command', '')
        # 截断过长的命令
        if len(command) > 50:
            command = command[:50] + '...'
        return f"Bash: {command}"

    elif tool_name == 'Task':
        description = tool_input.get('description', '')
        return f"Task: {description}"

    elif tool_name.startswith('mcp__'):
        # MCP 工具，提取简短名称
        short_name = tool_name.replace('mcp__', '').replace('__', '/')
        return f"MCP: {short_name}"

    else:
        # 其他工具，尝试提取常见参数
        if 'file_path' in tool_input:
            filename = tool_input['file_path'].split('/')[-1]
            return f"{tool_name}: {filename}"
        elif 'pattern' in tool_input:
            return f"{tool_name}: {tool_input['pattern']}"
        elif 'query' in tool_input:
            query = tool_input['query']
            if len(query) > 30:
                query = query[:30] + '...'
            return f"{tool_name}: {query}"
        else:
            return f"{tool_name}"


def run_single_mode_analysis(
    mode: str,
    prompt: str,
    output_dir: Path,
    repo_root: Path,
    result_filename: str,
    with_context: bool,
    model: str = None,
    diff_content: str = None
) -> Tuple[str, str, bool, str]:
    """
    运行单个模式的分析（用于并行执行）

    使用 --output-format stream-json --verbose 获取实时工具调用信息
    使用 --json-schema 强制输出符合指定格式的 JSON

    Args:
        mode: 模式（review/analyze/priority）
        prompt: 分析 prompt
        output_dir: 输出目录
        repo_root: 仓库根目录
        result_filename: 结果文件名
        with_context: 是否启用仓库上下文
        model: 指定使用的模型
        diff_content: git diff 输出内容，用于生成报告时展示代码变更

    Returns:
        (mode, result_filename, success, result_or_error)
    """
    # 定义各模式的必需字段
    mode_required_fields = {
        'review': ['findings', 'overall_correctness'],
        'analyze': ['change_summary', 'file_changes'],
        'priority': ['review_summary', 'priority_areas']
    }
    
    def is_valid_for_mode(data: dict, target_mode: str) -> bool:
        """检查数据是否包含指定模式的所有必需字段"""
        if target_mode not in mode_required_fields:
            return True
        required = mode_required_fields[target_mode]
        return all(field in data for field in required)
    
    try:
        thread_safe_print(f"[{mode}] 分析中...")

        # 构建 Claude 命令 - 使用 stream-json 格式获取工具调用信息
        cmd = ['claude', '-p', '--output-format', 'stream-json', '--verbose']
        
        # 添加 JSON Schema 强制输出格式
        if mode in JSON_SCHEMAS:
            schema_str = json.dumps(JSON_SCHEMAS[mode])
            cmd.extend(['--json-schema', schema_str])
        
        if model:
            cmd.extend(['--model', model])
        cmd.append('-')

        # 启动进程
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(repo_root) if with_context and repo_root else None
        )

        # 发送 prompt 并关闭 stdin
        process.stdin.write(prompt)
        process.stdin.close()

        # 实时读取输出并解析工具调用
        final_result = None
        structured_output = None  # 用于存储 StructuredOutput 工具调用的结果
        raw_output_lines = []

        for line in process.stdout:
            raw_output_lines.append(line)
            try:
                event = json.loads(line.strip())
                event_type = event.get('type')

                # 解析工具调用事件
                if event_type == 'assistant':
                    content = event.get('message', {}).get('content', [])
                    for item in content:
                        if item.get('type') == 'tool_use':
                            tool_name = item.get('name', 'unknown')
                            tool_input = item.get('input', {})
                            
                            # 检查是否是 StructuredOutput 工具调用
                            if tool_name == 'StructuredOutput':
                                # StructuredOutput 的 input 就是我们需要的 JSON 数据
                                # 只有当 input 非空且包含必需字段时才使用
                                if tool_input and len(tool_input) > 0 and is_valid_for_mode(tool_input, mode):
                                    structured_output = tool_input
                                thread_safe_print(f"[{mode}] StructuredOutput")
                            else:
                                # 格式化其他工具调用详情
                                detail = format_tool_call_detail(tool_name, tool_input)
                                thread_safe_print(f"[{mode}] {detail}")

                # 获取最终结果
                elif event_type == 'result':
                    final_result = event.get('result', '')

            except json.JSONDecodeError:
                pass

        # 等待进程结束
        process.wait()

        if process.returncode != 0:
            stderr = process.stderr.read()
            raise Exception(f"claude 命令执行失败:\n{stderr}")

        # 保存原始输出
        if output_dir:
            raw_output_file = output_dir / 'raw_output.txt'
            with open(raw_output_file, 'a', encoding='utf-8') as f:
                f.write(f"\n\n{'='*50}\n")
                f.write(f"Mode: {mode}\n")
                f.write(f"{'='*50}\n\n")
                f.write(''.join(raw_output_lines))

        # 优先使用有效的 StructuredOutput 工具调用的结果
        json_data = None
        if structured_output is not None and len(structured_output) > 0:
            json_data = structured_output
        
        # 如果 StructuredOutput 无效或为空，从 final_result 中提取
        if json_data is None or not is_valid_for_mode(json_data, mode):
            raw_output = final_result if final_result else ''.join(raw_output_lines)
            extracted = extract_json_from_text(raw_output, mode)
            if extracted and is_valid_for_mode(extracted, mode):
                json_data = extracted

        if json_data is None or (isinstance(json_data, dict) and len(json_data) == 0):
            thread_safe_print(f"[{mode}] 警告: 无法从输出中提取有效的 JSON")
            if mode == "review":
                fallback = create_fallback_review("无法提取 JSON")
                result_str = format_json(fallback)
            else:
                # 对于 analyze 和 priority 模式，也创建一个空的 fallback
                result_str = format_json({})
        elif mode == "review" and not validate_review_schema(json_data):
            thread_safe_print(f"[{mode}] 警告: 输出不符合预期的 schema")
            fallback = create_fallback_review("Schema 验证失败")
            result_str = format_json(fallback)
        else:
            result_str = format_json(json_data)

        # 保存结果
        result_file = output_dir / result_filename
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(result_str)

        # 生成 HTML 报告
        generate_html_report(result_file, mode, diff_content)

        thread_safe_print(f"[{mode}] ✓ 完成")
        return (mode, result_filename, True, result_str)

    except Exception as e:
        thread_safe_print(f"[{mode}] ✗ 失败: {e}")
        return (mode, result_filename, False, str(e))


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
  # 完整分析（同时运行三种模式）
  %(prog)s -a 100027304 -b main -t feature/test

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
                       help='只生成 prompt，不调用 Claude')
    parser.add_argument('--no-context', action='store_true',
                       help='禁用仓库上下文访问（默认启用）：不在仓库目录下运行 Claude')
    parser.add_argument('--model', '-M',
                       default=None,
                       help='指定 Claude 使用的模型（如 sonnet, opus, claude-sonnet-4-5-20250929）')
    parser.add_argument('--no-update', action='store_true',
                       help='跳过仓库更新（默认会自动 fetch 并更新分支）')
    parser.add_argument('--sequential', action='store_true',
                       help='串行执行所有模式（默认 all 模式下并行执行）')

    args = parser.parse_args()

    # 默认启用仓库上下文访问，除非指定 --no-context
    with_context = not args.no_context

    try:
        # 1. 查找 git 项目
        search_root = Path(args.search_root).expanduser()  # 展开 ~ 为用户目录
        if not search_root.exists():
            print(f"搜索目录不存在，正在创建: {search_root}")
            search_root.mkdir(parents=True, exist_ok=True)
        repo_root = find_repo_by_appid(search_root, args.appid)
        print(f"找到项目: {repo_root}")

        # 2. 更新仓库（默认启用，除非指定 --no-update）
        if not args.no_update:
            update_repo(repo_root, args.basebranch, args.targetbranch)

        # 3. 获取 git diff 信息
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
        print(f"输出目录: {output_dir}")

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
                exec_mode = "串行" if args.sequential else "并行"
                print(f"{exec_mode}运行 {len(modes_to_run)} 个模式: {', '.join(modes_to_run)} (Claude)")
            else:
                print(f"运行模式: {modes_to_run[0]} (Claude)")
            if with_context:
                print(f"仓库上下文: 已启用（工作目录: {repo_root}）")
            print(f"{'='*50}")

            results = {}

            # 提取 diff 内容用于报告展示
            diff_content = diff[0] if diff else None

            if len(modes_to_run) == 1 or args.sequential:
                # 串行执行（单模式或指定 --sequential）
                for mode in modes_to_run:
                    config = mode_configs[mode]
                    mode_result = run_single_mode_analysis(
                        mode, config['prompt'], output_dir, repo_root, config['result_filename'], with_context,
                        model=args.model, diff_content=diff_content
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
                            mode, config['prompt'], output_dir, repo_root, config['result_filename'], with_context,
                            args.model, diff_content
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
                combined_html = generate_combined_report(analyze_data, priority_data, review_data, diff_content)
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

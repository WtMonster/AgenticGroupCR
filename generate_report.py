#!/usr/bin/env python3
"""
HTML 报告生成工具
将 JSON 格式的分析结果转换为可视化的 HTML 报告

支持三种报告类型：
1. review - 代码审查报告
2. analyze - 代码变更解析报告
3. priority - Review 优先级评估报告
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


def load_json_file(file_path: str) -> Dict[str, Any]:
    """加载 JSON 文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise Exception(f"加载 JSON 文件失败: {e}")


def parse_diff_to_file_hunks(diff_content: str) -> Dict[str, List[dict]]:
    """
    解析 git diff 输出，按文件组织 hunks
    
    Args:
        diff_content: git diff 的完整输出
    
    Returns:
        dict: {文件路径: [hunk1, hunk2, ...]}
        每个 hunk 包含: {
            'old_start': int,  # 旧文件起始行
            'old_count': int,  # 旧文件行数
            'new_start': int,  # 新文件起始行
            'new_count': int,  # 新文件行数
            'lines': [{'type': '+'/'-'/' ', 'content': str, 'old_line': int|None, 'new_line': int|None}, ...]
        }
    """
    if not diff_content:
        return {}
    
    file_hunks = {}
    current_file = None
    current_hunk = None
    old_line = 0
    new_line = 0
    
    lines = diff_content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # 检测文件头: diff --git a/path b/path
        if line.startswith('diff --git '):
            # 提取文件路径 (取 b/ 后面的路径)
            parts = line.split(' b/')
            if len(parts) >= 2:
                current_file = parts[-1]
                if current_file not in file_hunks:
                    file_hunks[current_file] = []
            current_hunk = None
        
        # 检测 hunk 头: @@ -old_start,old_count +new_start,new_count @@
        elif line.startswith('@@') and current_file:
            import re
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if match:
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1
                
                current_hunk = {
                    'old_start': old_start,
                    'old_count': old_count,
                    'new_start': new_start,
                    'new_count': new_count,
                    'header': line,
                    'lines': []
                }
                file_hunks[current_file].append(current_hunk)
                old_line = old_start
                new_line = new_start
        
        # 解析 hunk 内容
        elif current_hunk is not None:
            if line.startswith('+') and not line.startswith('+++'):
                current_hunk['lines'].append({
                    'type': '+',
                    'content': line[1:],
                    'old_line': None,
                    'new_line': new_line
                })
                new_line += 1
            elif line.startswith('-') and not line.startswith('---'):
                current_hunk['lines'].append({
                    'type': '-',
                    'content': line[1:],
                    'old_line': old_line,
                    'new_line': None
                })
                old_line += 1
            elif line.startswith(' '):
                current_hunk['lines'].append({
                    'type': ' ',
                    'content': line[1:],
                    'old_line': old_line,
                    'new_line': new_line
                })
                old_line += 1
                new_line += 1
            elif line.startswith('\\'):
                # "\ No newline at end of file"
                pass
            elif line == '':
                # 空行可能是 hunk 结束
                pass
        
        i += 1
    
    return file_hunks


def format_diff_hunk_html(hunk: dict, file_path: str = "", highlight_start: int = 0, highlight_end: int = 0) -> str:
    """
    将 diff hunk 格式化为 GitHub/GitLab 风格的 HTML
    
    Args:
        hunk: 解析后的 hunk 数据
        file_path: 文件路径
        highlight_start: 需要高亮的起始行号（新文件行号）
        highlight_end: 需要高亮的结束行号（新文件行号）
    
    Returns:
        HTML 格式的 diff 片段
    """
    if not hunk or not hunk.get('lines'):
        return ""
    
    html = '<div class="diff-hunk">\n'
    
    # Hunk 头部
    header = hunk.get('header', '')
    if header:
        escaped_header = header.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html += f'<div class="diff-hunk-header">{escaped_header}</div>\n'
    
    html += '<table class="diff-table">\n'
    
    for line_info in hunk['lines']:
        line_type = line_info['type']
        content = line_info['content']
        old_line = line_info.get('old_line')
        new_line = line_info.get('new_line')
        
        # HTML 转义
        escaped_content = (content
                          .replace('&', '&amp;')
                          .replace('<', '&lt;')
                          .replace('>', '&gt;'))
        
        # 保留空格显示
        if not escaped_content:
            escaped_content = '&nbsp;'
        
        # 根据类型设置样式
        if line_type == '+':
            row_class = 'diff-line-add'
            prefix = '+'
            old_num = ''
            new_num = str(new_line) if new_line else ''
        elif line_type == '-':
            row_class = 'diff-line-del'
            prefix = '-'
            old_num = str(old_line) if old_line else ''
            new_num = ''
        else:
            row_class = 'diff-line-ctx'
            prefix = ' '
            old_num = str(old_line) if old_line else ''
            new_num = str(new_line) if new_line else ''
        
        # 检查是否需要标记行号（AI 评论指出的行）
        line_num_class = ''
        if highlight_start > 0 and highlight_end > 0 and new_line:
            if highlight_start <= new_line <= highlight_end:
                line_num_class = ' diff-line-num-marked'
        
        html += f'<tr class="{row_class}">'
        html += f'<td class="diff-line-num diff-line-num-old{line_num_class}">{old_num}</td>'
        html += f'<td class="diff-line-num diff-line-num-new{line_num_class}">{new_num}</td>'
        html += f'<td class="diff-line-prefix">{prefix}</td>'
        html += f'<td class="diff-line-content"><pre>{escaped_content}</pre></td>'
        html += '</tr>\n'
    
    html += '</table>\n'
    html += '</div>\n'
    
    return html


def get_diff_snippet_for_finding(
    code_location: dict, 
    diff_content: str = None,
    file_hunks: Dict[str, List[dict]] = None
) -> str:
    """
    根据 finding 的 code_location 从 diff 中提取相关片段
    
    Args:
        code_location: 包含 absolute_file_path 和 line_range 的字典
        diff_content: git diff 的原始输出（如果 file_hunks 未提供）
        file_hunks: 已解析的 diff hunks（优先使用）
    
    Returns:
        HTML 格式的 diff 片段，如果无法匹配则返回空字符串
    """
    if not code_location:
        return ""
    
    file_path = code_location.get('absolute_file_path', '')
    line_range = code_location.get('line_range', {})

    if not file_path:
        return ""

    # 处理 line_range 可能是数组 [start, end] 或对象 {"start": x, "end": y} 的情况
    if isinstance(line_range, list):
        start_line = line_range[0] if len(line_range) > 0 else 0
        end_line = line_range[1] if len(line_range) > 1 else start_line
    else:
        start_line = line_range.get('start', 0) if isinstance(line_range, dict) else 0
        end_line = line_range.get('end', start_line) if isinstance(line_range, dict) else start_line
    
    # 解析 diff（如果需要）
    if file_hunks is None and diff_content:
        file_hunks = parse_diff_to_file_hunks(diff_content)
    
    if not file_hunks:
        return ""
    
    # 尝试匹配文件路径
    # AI 可能返回绝对路径或相对路径，需要灵活匹配
    matched_file = None
    file_path_normalized = file_path.replace('\\', '/')
    
    for diff_file in file_hunks.keys():
        # 完全匹配
        if diff_file == file_path_normalized:
            matched_file = diff_file
            break
        # 文件名匹配（diff 中通常是相对路径）
        if file_path_normalized.endswith('/' + diff_file) or file_path_normalized.endswith(diff_file):
            matched_file = diff_file
            break
        # diff 文件路径是 file_path 的后缀
        if diff_file.endswith(file_path_normalized.split('/')[-1]):
            # 进一步检查路径是否匹配
            diff_parts = diff_file.split('/')
            path_parts = file_path_normalized.split('/')
            # 从后往前匹配
            match_count = 0
            for i in range(1, min(len(diff_parts), len(path_parts)) + 1):
                if diff_parts[-i] == path_parts[-i]:
                    match_count += 1
                else:
                    break
            if match_count >= 1:  # 至少文件名匹配
                matched_file = diff_file
                break
    
    if not matched_file:
        return ""
    
    hunks = file_hunks[matched_file]
    if not hunks:
        return ""
    
    # 找到与行号范围相关的 hunk
    relevant_hunks = []
    for hunk in hunks:
        hunk_new_start = hunk['new_start']
        hunk_new_end = hunk_new_start + hunk['new_count'] - 1
        
        # 检查是否有重叠
        if start_line <= 0:
            # 如果没有指定行号，返回第一个 hunk
            relevant_hunks.append(hunk)
            break
        elif not (end_line < hunk_new_start or start_line > hunk_new_end):
            relevant_hunks.append(hunk)
    
    # 如果没有找到相关 hunk，返回第一个 hunk 作为参考
    if not relevant_hunks and hunks:
        relevant_hunks = [hunks[0]]
    
    # 生成 HTML，包含行号范围提示
    html = f'<div class="diff-file" data-file="{matched_file}">\n'
    html += f'<div class="diff-file-header">'
    html += f'<span class="diff-file-name">{matched_file}</span>'
    if start_line > 0:
        html += f'<span class="diff-line-range-badge">行 {start_line}-{end_line}</span>'
    html += '</div>\n'
    
    for hunk in relevant_hunks:
        # 传递高亮行号范围
        html += format_diff_hunk_html(hunk, matched_file, start_line, end_line)
    
    html += '</div>\n'
    
    return html


def get_diff_for_file(file_path: str, file_hunks: Dict[str, List[dict]]) -> str:
    """
    获取指定文件的完整 diff HTML
    
    Args:
        file_path: 文件路径
        file_hunks: 已解析的 diff hunks
    
    Returns:
        HTML 格式的 diff，如果无法匹配则返回空字符串
    """
    if not file_path or not file_hunks:
        return ""
    
    # 尝试匹配文件路径
    file_path_normalized = file_path.replace('\\', '/')
    matched_file = None
    
    for diff_file in file_hunks.keys():
        # 完全匹配
        if diff_file == file_path_normalized:
            matched_file = diff_file
            break
        # 文件名匹配
        if file_path_normalized.endswith('/' + diff_file) or file_path_normalized.endswith(diff_file):
            matched_file = diff_file
            break
        # diff 文件路径匹配 file_path 的后缀
        file_name = file_path_normalized.split('/')[-1]
        if diff_file.endswith(file_name):
            # 进一步检查路径
            diff_parts = diff_file.split('/')
            path_parts = file_path_normalized.split('/')
            match_count = 0
            for i in range(1, min(len(diff_parts), len(path_parts)) + 1):
                if diff_parts[-i] == path_parts[-i]:
                    match_count += 1
                else:
                    break
            if match_count >= 1:
                matched_file = diff_file
                break
    
    if not matched_file:
        return ""
    
    hunks = file_hunks[matched_file]
    if not hunks:
        return ""
    
    # 生成 HTML
    html = f'<div class="diff-file" data-file="{matched_file}">\n'
    html += f'<div class="diff-file-header">{matched_file}</div>\n'
    
    for hunk in hunks:
        html += format_diff_hunk_html(hunk, matched_file)
    
    html += '</div>\n'
    
    return html


def detect_report_type(data: Dict[str, Any]) -> str:
    """自动检测报告类型"""
    if 'findings' in data and 'overall_correctness' in data:
        return 'review'
    elif 'change_summary' in data and 'file_changes' in data:
        return 'analyze'
    elif 'review_summary' in data and 'priority_areas' in data:
        return 'priority'
    else:
        return 'unknown'


def generate_html_header(title: str) -> str:
    """生成 HTML 头部"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 30px;
            font-size: 32px;
        }}

        h2 {{
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            font-size: 24px;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }}

        h3 {{
            color: #555;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 18px;
        }}

        .meta-info {{
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}

        .meta-info p {{
            margin: 5px 0;
            color: #555;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 8px;
        }}

        .badge-high {{
            background: #e74c3c;
            color: white;
        }}

        .badge-medium {{
            background: #f39c12;
            color: white;
        }}

        .badge-low {{
            background: #95a5a6;
            color: white;
        }}

        .badge-feature {{
            background: #3498db;
            color: white;
        }}

        .badge-bugfix {{
            background: #e74c3c;
            color: white;
        }}

        .badge-refactor {{
            background: #9b59b6;
            color: white;
        }}

        .badge-success {{
            background: #27ae60;
            color: white;
        }}

        .card {{
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .card-header {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 15px;
            color: #2c3e50;
        }}

        .finding {{
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin-bottom: 25px;
        }}

        .finding-high {{
            border-left-color: #e74c3c;
        }}

        .finding-medium {{
            border-left-color: #f39c12;
        }}

        .finding-low {{
            border-left-color: #95a5a6;
        }}

        .code-location {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 13px;
            margin: 10px 0;
        }}

        /* GitHub/GitLab 风格 Diff 样式 */
        .diff-file {{
            border: 1px solid #d0d7de;
            border-radius: 6px;
            margin: 12px 0;
            overflow: hidden;
            background: #ffffff;
        }}

        .diff-file-header {{
            background: #f6f8fa;
            border-bottom: 1px solid #d0d7de;
            padding: 10px 16px;
            font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            color: #24292f;
            font-weight: 600;
        }}

        .diff-hunk {{
            border-top: 1px solid #d0d7de;
        }}

        .diff-hunk:first-child {{
            border-top: none;
        }}

        .diff-hunk-header {{
            background: #f1f8ff;
            color: #57606a;
            padding: 8px 16px;
            font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            border-bottom: 1px solid #d0d7de;
        }}

        .diff-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            line-height: 20px;
        }}

        .diff-table tr {{
            border: none;
        }}

        /* 新增行 - 绿色背景 */
        .diff-line-add {{
            background-color: #e6ffec;
        }}

        .diff-line-add .diff-line-num {{
            background-color: #ccffd8;
            color: #24292f;
        }}

        .diff-line-add .diff-line-prefix {{
            color: #1a7f37;
        }}

        .diff-line-add .diff-line-content {{
            background-color: #e6ffec;
        }}

        /* 删除行 - 红色背景 */
        .diff-line-del {{
            background-color: #ffebe9;
        }}

        .diff-line-del .diff-line-num {{
            background-color: #ffd7d5;
            color: #24292f;
        }}

        .diff-line-del .diff-line-prefix {{
            color: #cf222e;
        }}

        .diff-line-del .diff-line-content {{
            background-color: #ffebe9;
        }}

        /* 上下文行 */
        .diff-line-ctx {{
            background-color: #ffffff;
        }}

        .diff-line-ctx .diff-line-num {{
            background-color: #f6f8fa;
            color: #57606a;
        }}

        .diff-line-ctx .diff-line-prefix {{
            color: #57606a;
        }}

        /* AI 评论标记的行号（红色） */
        .diff-line-num-marked {{
            background-color: #dc2626 !important;
            color: #ffffff !important;
            font-weight: bold;
        }}

        /* 文件头中的行号范围徽章 */
        .diff-file-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .diff-file-name {{
            font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
            font-size: 13px;
            font-weight: 600;
            color: #24292f;
        }}

        .diff-line-range-badge {{
            background: #f59e0b;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: bold;
        }}

        /* 行号列 */
        .diff-line-num {{
            width: 40px;
            min-width: 40px;
            padding: 0 8px;
            text-align: right;
            user-select: none;
            vertical-align: top;
            color: #57606a;
            border-right: 1px solid #d0d7de;
        }}

        .diff-line-num-old {{
            border-right: none;
        }}

        .diff-line-num-new {{
            border-right: 1px solid #d0d7de;
        }}

        /* 前缀列 (+/-/空格) */
        .diff-line-prefix {{
            width: 20px;
            min-width: 20px;
            padding: 0 4px;
            text-align: center;
            user-select: none;
            font-weight: bold;
        }}

        /* 代码内容列 */
        .diff-line-content {{
            padding: 0 16px 0 8px;
            white-space: pre;
            overflow-x: auto;
            color: #24292f;
        }}

        .diff-line-content pre {{
            margin: 0;
            padding: 0;
            font-family: inherit;
            font-size: inherit;
            white-space: pre;
            background: transparent;
            color: inherit;
            display: inline;
        }}

        ul {{
            margin: 10px 0;
            padding-left: 25px;
        }}

        li {{
            margin: 8px 0;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}

        .summary-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }}

        .summary-value {{
            font-size: 32px;
            font-weight: bold;
            color: #3498db;
            margin: 10px 0;
        }}

        .summary-label {{
            color: #666;
            font-size: 14px;
        }}

        .progress-bar {{
            background: #ecf0f1;
            height: 20px;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}

        .progress-fill {{
            background: #3498db;
            height: 100%;
            transition: width 0.3s ease;
        }}

        .file-change {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            border-left: 3px solid #3498db;
        }}

        .file-path {{
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 14px;
            color: #2c3e50;
            font-weight: bold;
            margin-bottom: 10px;
        }}

        .stats {{
            color: #666;
            font-size: 13px;
            margin: 5px 0;
        }}

        .stats-add {{
            color: #27ae60;
        }}

        .stats-delete {{
            color: #e74c3c;
        }}

        .priority-area {{
            background: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}

        .priority-high {{
            border-color: #e74c3c;
            background: #fff5f5;
        }}

        .priority-medium {{
            border-color: #f39c12;
            background: #fffbf0;
        }}

        .priority-low {{
            border-color: #95a5a6;
            background: #f8f9fa;
        }}

        .time-estimate {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 5px 15px;
            border-radius: 15px;
            font-size: 14px;
            margin: 10px 0;
        }}

        .confidence-score {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            margin: 10px 0;
        }}

        .confidence-high {{
            background: #d4edda;
            color: #155724;
        }}

        .confidence-medium {{
            background: #fff3cd;
            color: #856404;
        }}

        .confidence-low {{
            background: #f8d7da;
            color: #721c24;
        }}

        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #999;
            font-size: 14px;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
"""


def generate_html_footer() -> str:
    """生成 HTML 尾部"""
    return f"""
        <div class="footer">
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>由 Claude Code Review Tool 生成</p>
        </div>
    </div>
</body>
</html>
"""


def get_confidence_class(score: float) -> str:
    """获取置信度样式类"""
    if score >= 0.8:
        return "confidence-high"
    elif score >= 0.5:
        return "confidence-medium"
    else:
        return "confidence-low"


def get_priority_badge(priority: str) -> str:
    """获取优先级徽章"""
    priority_map = {
        'high': 'badge-high',
        'medium': 'badge-medium',
        'low': 'badge-low'
    }
    return f'<span class="badge {priority_map.get(priority, "badge-low")}">{priority.upper()}</span>'


def generate_review_report(data: Dict[str, Any], diff_content: str = None) -> str:
    """生成代码审查报告
    
    Args:
        data: 审查结果数据
        diff_content: git diff 输出内容，用于展示代码变更
    """
    html = generate_html_header("代码审查报告")

    html += "<h1>📋 代码审查报告</h1>\n"
    
    # 预解析 diff（避免重复解析）
    file_hunks = None
    if diff_content:
        file_hunks = parse_diff_to_file_hunks(diff_content)

    # 总体评估
    html += "<h2>总体评估</h2>\n"
    html += '<div class="card">\n'
    html += f'<p><strong>整体正确性:</strong> '
    if data.get('overall_correctness') == 'patch is correct':
        html += '<span class="badge badge-success">✓ 代码正确</span>'
    else:
        html += '<span class="badge badge-high">✗ 存在问题</span>'
    html += '</p>\n'

    html += f'<p><strong>整体说明:</strong> {data.get("overall_explanation", "无")}</p>\n'

    confidence = data.get('overall_confidence_score', 0)
    html += f'<p><strong>置信度:</strong> <span class="confidence-score {get_confidence_class(confidence)}">{confidence:.0%}</span></p>\n'
    html += '</div>\n'

    # 发现的问题
    findings = data.get('findings', [])
    html += f"<h2>发现的问题 ({len(findings)})</h2>\n"

    if not findings:
        html += '<div class="card"><p>✓ 未发现明显问题</p></div>\n'
    else:
        for idx, finding in enumerate(findings, 1):
            priority = 'medium'  # 默认优先级
            if '[P0]' in finding.get('title', '') or '[P1]' in finding.get('title', ''):
                priority = 'high'
            elif '[P3]' in finding.get('title', ''):
                priority = 'low'

            html += f'<div class="finding finding-{priority}">\n'
            html += f'<h3>{idx}. {finding.get("title", "未命名问题")}</h3>\n'
            html += f'<p>{finding.get("body", "")}</p>\n'

            # 代码位置
            code_loc = finding.get('code_location', {})
            if code_loc:
                html += '<div class="code-location">\n'
                html += f'<strong>文件:</strong> {code_loc.get("absolute_file_path", "未知")}<br>\n'
                line_range = code_loc.get('line_range', {})
                if line_range:
                    # 处理 line_range 可能是数组或对象的情况
                    if isinstance(line_range, list):
                        start = line_range[0] if len(line_range) > 0 else "?"
                        end = line_range[1] if len(line_range) > 1 else start
                    else:
                        start = line_range.get("start", "?")
                        end = line_range.get("end", "?")
                    html += f'<strong>行号:</strong> {start} - {end}\n'
                html += '</div>\n'
                
                # 添加 diff 代码片段
                if file_hunks:
                    diff_snippet_html = get_diff_snippet_for_finding(code_loc, file_hunks=file_hunks)
                    if diff_snippet_html:
                        html += diff_snippet_html

            # 置信度
            conf = finding.get('confidence_score', 0)
            html += f'<p><small>置信度: <span class="confidence-score {get_confidence_class(conf)}">{conf:.0%}</span></small></p>\n'
            html += '</div>\n'

    html += generate_html_footer()
    return html


def generate_analyze_report(data: Dict[str, Any], diff_content: str = None) -> str:
    """生成代码变更解析报告
    
    Args:
        data: 变更解析数据
        diff_content: git diff 输出内容，用于展示代码变更
    """
    html = generate_html_header("代码变更解析报告")

    html += "<h1>🔍 代码变更解析报告</h1>\n"
    
    # 预解析 diff
    file_hunks = None
    if diff_content:
        file_hunks = parse_diff_to_file_hunks(diff_content)

    # 变更总览
    summary = data.get('change_summary', {})
    html += "<h2>变更总览</h2>\n"
    html += '<div class="card">\n'
    html += f'<h3>{summary.get("title", "未命名变更")}</h3>\n'

    # 类型和风险徽章
    change_type = summary.get('type', 'unknown')
    risk_level = summary.get('risk_level', 'medium')
    html += f'<p>{get_type_badge(change_type)} {get_priority_badge(risk_level)}</p>\n'

    html += f'<p><strong>变更目的:</strong> {summary.get("purpose", "未说明")}</p>\n'
    html += f'<p><strong>变更范围:</strong> {summary.get("scope", "未说明")}</p>\n'
    html += f'<p><strong>复杂度:</strong> {summary.get("estimated_complexity", "未知")}</p>\n'

    confidence = summary.get('confidence_score', data.get('confidence_score', 0))
    html += f'<p><strong>置信度:</strong> <span class="confidence-score {get_confidence_class(confidence)}">{confidence:.0%}</span></p>\n'
    html += '</div>\n'

    # 文件变更
    file_changes = data.get('file_changes', [])
    html += f"<h2>文件变更详情 ({len(file_changes)})</h2>\n"

    for change in file_changes:
        html += '<div class="file-change">\n'
        file_path = change.get("file_path", "未知文件")
        html += f'<div class="file-path">{file_path}</div>\n'
        html += f'<p><span class="badge badge-feature">{change.get("change_type", "unknown").upper()}</span></p>\n'

        lines_add = change.get('lines_added', 0)
        lines_del = change.get('lines_deleted', 0)
        html += f'<p class="stats"><span class="stats-add">+{lines_add}</span> / <span class="stats-delete">-{lines_del}</span></p>\n'

        html += f'<p><strong>目的:</strong> {change.get("purpose", "未说明")}</p>\n'

        key_changes = change.get('key_changes', [])
        if key_changes:
            html += '<p><strong>关键变更:</strong></p>\n<ul>\n'
            for kc in key_changes:
                html += f'<li>{kc}</li>\n'
            html += '</ul>\n'

        html += f'<p><strong>影响:</strong> {change.get("impact", "未说明")}</p>\n'
        
        # 添加该文件的 diff 展示
        if file_hunks:
            diff_html = get_diff_for_file(file_path, file_hunks)
            if diff_html:
                html += diff_html
        
        html += '</div>\n'

    # 架构影响
    arch_impact = data.get('architecture_impact', {})
    if arch_impact and any(arch_impact.values()):
        html += "<h2>架构影响</h2>\n"
        html += '<div class="card">\n'

        if arch_impact.get('affected_modules'):
            html += '<p><strong>受影响模块:</strong></p>\n<ul>\n'
            for module in arch_impact['affected_modules']:
                html += f'<li>{module}</li>\n'
            html += '</ul>\n'

        if arch_impact.get('new_dependencies'):
            html += '<p><strong>新增依赖:</strong></p>\n<ul>\n'
            for dep in arch_impact['new_dependencies']:
                html += f'<li>{dep}</li>\n'
            html += '</ul>\n'

        if arch_impact.get('api_changes'):
            html += '<p><strong>API 变更:</strong></p>\n<ul>\n'
            for api in arch_impact['api_changes']:
                html += f'<li>{api}</li>\n'
            html += '</ul>\n'

        html += '</div>\n'

    # 迁移注意事项
    migration_notes = data.get('migration_notes', [])
    if migration_notes:
        html += "<h2>⚠️ 迁移注意事项</h2>\n"
        html += '<div class="card">\n<ul>\n'
        for note in migration_notes:
            html += f'<li>{note}</li>\n'
        html += '</ul>\n</div>\n'

    html += generate_html_footer()
    return html


def generate_priority_report(data: Dict[str, Any], diff_content: str = None) -> str:
    """生成 Review 优先级评估报告
    
    Args:
        data: 优先级评估数据
        diff_content: git diff 输出内容，用于展示代码变更
    """
    html = generate_html_header("Review 优先级评估报告")

    html += "<h1>⭐ Review 优先级评估报告</h1>\n"
    
    # 预解析 diff
    file_hunks = None
    if diff_content:
        file_hunks = parse_diff_to_file_hunks(diff_content)

    # Review 总览
    summary = data.get('review_summary', {})
    html += "<h2>Review 总览</h2>\n"

    html += '<div class="summary-grid">\n'
    html += f'''
        <div class="summary-item">
            <div class="summary-label">总文件数</div>
            <div class="summary-value">{summary.get('total_files', 0)}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">高优先级</div>
            <div class="summary-value" style="color: #e74c3c;">{summary.get('high_priority_files', 0)}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">中优先级</div>
            <div class="summary-value" style="color: #f39c12;">{summary.get('medium_priority_files', 0)}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">低优先级</div>
            <div class="summary-value" style="color: #95a5a6;">{summary.get('low_priority_files', 0)}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">预估时长</div>
            <div class="summary-value">{summary.get('estimated_total_minutes', 0)}</div>
            <div class="summary-label">分钟</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">建议 Reviewer</div>
            <div class="summary-value">{summary.get('recommended_reviewers', 1)}</div>
            <div class="summary-label">人</div>
        </div>
    '''
    html += '</div>\n'

    # 优先级区域
    priority_areas = data.get('priority_areas', [])
    html += f"<h2>重点 Review 区域 ({len(priority_areas)})</h2>\n"

    for idx, area in enumerate(priority_areas, 1):
        priority = area.get('priority', 'medium')
        html += f'<div class="priority-area priority-{priority}">\n'
        file_path = area.get("file_path", "未知文件")
        html += f'<h3>{idx}. {file_path}</h3>\n'
        html += f'<p>{get_priority_badge(priority)} '

        line_range = area.get('line_range', {})
        if line_range:
            # 处理 line_range 可能是数组或对象的情况
            if isinstance(line_range, list):
                start = line_range[0] if len(line_range) > 0 else "?"
                end = line_range[1] if len(line_range) > 1 else start
            else:
                start = line_range.get("start", "?")
                end = line_range.get("end", "?")
            html += f'<span class="code-location">行 {start} - {end}</span>'
        html += '</p>\n'

        html += f'<p><strong>原因:</strong> {area.get("reason", "未说明")}</p>\n'

        focus_points = area.get('focus_points', [])
        if focus_points:
            html += '<p><strong>关注点:</strong></p>\n<ul>\n'
            for fp in focus_points:
                html += f'<li>{fp}</li>\n'
            html += '</ul>\n'

        minutes = area.get('estimated_minutes', 0)
        html += f'<p><span class="time-estimate">⏱️ 预估 {minutes} 分钟</span></p>\n'

        risk_factors = area.get('risk_factors', [])
        if risk_factors:
            html += '<p><strong>⚠️ 风险因素:</strong></p>\n<ul>\n'
            for rf in risk_factors:
                html += f'<li>{rf}</li>\n'
            html += '</ul>\n'
        
        # 添加 diff 代码片段
        if file_hunks:
            # 构造 code_location 格式
            code_loc = {
                'absolute_file_path': file_path,
                'line_range': line_range
            }
            diff_snippet_html = get_diff_snippet_for_finding(code_loc, file_hunks=file_hunks)
            if diff_snippet_html:
                html += diff_snippet_html

        html += '</div>\n'

    # Review 策略
    strategy = data.get('review_strategy', {})
    if strategy:
        html += "<h2>Review 策略</h2>\n"
        html += '<div class="card">\n'

        recommended_order = strategy.get('recommended_order', [])
        if recommended_order:
            html += '<p><strong>推荐顺序:</strong></p>\n<ol>\n'
            for order in recommended_order:
                html += f'<li>{order}</li>\n'
            html += '</ol>\n'

        prerequisites = strategy.get('prerequisites', [])
        if prerequisites:
            html += '<p><strong>前置知识:</strong></p>\n<ul>\n'
            for prereq in prerequisites:
                html += f'<li>{prereq}</li>\n'
            html += '</ul>\n'

        html += '</div>\n'

    # 时间分解
    time_breakdown = data.get('time_breakdown', {})
    if time_breakdown:
        html += "<h2>时间分解</h2>\n"
        html += '<div class="card">\n'

        total = time_breakdown.get('total', 0)
        for key, value in time_breakdown.items():
            if key != 'total' and value > 0:
                percentage = (value / total * 100) if total > 0 else 0
                label_map = {
                    'code_reading': '代码阅读',
                    'logic_verification': '逻辑验证',
                    'testing_review': '测试审查',
                    'documentation_review': '文档审查',
                    'discussion_buffer': '讨论缓冲'
                }
                label = label_map.get(key, key)
                html += f'<p><strong>{label}:</strong> {value} 分钟 ({percentage:.0f}%)</p>\n'
                html += f'<div class="progress-bar"><div class="progress-fill" style="width: {percentage}%"></div></div>\n'

        html += f'<p><strong>总计:</strong> {total} 分钟</p>\n'
        html += '</div>\n'

    # 可跳过文件
    skip_files = data.get('skip_review_files', [])
    if skip_files:
        html += "<h2>可快速浏览的文件</h2>\n"
        html += '<div class="card">\n<ul>\n'
        for sf in skip_files:
            html += f'<li><code>{sf.get("file_path", "")}</code> - {sf.get("reason", "")}</li>\n'
        html += '</ul>\n</div>\n'

    html += generate_html_footer()
    return html


def get_type_badge(change_type: str) -> str:
    """获取变更类型徽章"""
    type_map = {
        'feature': ('badge-feature', '新功能'),
        'bugfix': ('badge-bugfix', 'Bug修复'),
        'refactor': ('badge-refactor', '重构'),
        'docs': ('badge-low', '文档'),
        'test': ('badge-low', '测试'),
        'chore': ('badge-low', '杂项')
    }
    badge_class, label = type_map.get(change_type, ('badge-low', change_type))
    return f'<span class="badge {badge_class}">{label}</span>'


def generate_combined_html_header(title: str) -> str:
    """生成合并报告的 HTML 头部（带 Tab 切换功能）"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 30px;
            font-size: 32px;
        }}

        h2 {{
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            font-size: 24px;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }}

        h3 {{
            color: #555;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 18px;
        }}

        /* Tab 样式 */
        .tab-container {{
            margin-bottom: 30px;
        }}

        .tab-buttons {{
            display: flex;
            border-bottom: 2px solid #e0e0e0;
            margin-bottom: 0;
        }}

        .tab-button {{
            padding: 15px 30px;
            border: none;
            background: #f5f5f5;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            color: #666;
            transition: all 0.3s ease;
            border-radius: 8px 8px 0 0;
            margin-right: 5px;
        }}

        .tab-button:hover {{
            background: #e8e8e8;
            color: #333;
        }}

        .tab-button.active {{
            background: #3498db;
            color: white;
        }}

        .tab-button.active:hover {{
            background: #2980b9;
        }}

        .tab-content {{
            display: none;
            padding: 30px 0;
        }}

        .tab-content.active {{
            display: block;
        }}

        .meta-info {{
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}

        .meta-info p {{
            margin: 5px 0;
            color: #555;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 8px;
        }}

        .badge-high {{
            background: #e74c3c;
            color: white;
        }}

        .badge-medium {{
            background: #f39c12;
            color: white;
        }}

        .badge-low {{
            background: #95a5a6;
            color: white;
        }}

        .badge-feature {{
            background: #3498db;
            color: white;
        }}

        .badge-bugfix {{
            background: #e74c3c;
            color: white;
        }}

        .badge-refactor {{
            background: #9b59b6;
            color: white;
        }}

        .badge-success {{
            background: #27ae60;
            color: white;
        }}

        .card {{
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .card-header {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 15px;
            color: #2c3e50;
        }}

        .finding {{
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin-bottom: 25px;
        }}

        .finding-high {{
            border-left-color: #e74c3c;
        }}

        .finding-medium {{
            border-left-color: #f39c12;
        }}

        .finding-low {{
            border-left-color: #95a5a6;
        }}

        .code-location {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 13px;
            margin: 10px 0;
        }}

        /* GitHub/GitLab 风格 Diff 样式 */
        .diff-file {{
            border: 1px solid #d0d7de;
            border-radius: 6px;
            margin: 12px 0;
            overflow: hidden;
            background: #ffffff;
        }}

        .diff-file-header {{
            background: #f6f8fa;
            border-bottom: 1px solid #d0d7de;
            padding: 10px 16px;
            font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            color: #24292f;
            font-weight: 600;
        }}

        .diff-hunk {{
            border-top: 1px solid #d0d7de;
        }}

        .diff-hunk:first-child {{
            border-top: none;
        }}

        .diff-hunk-header {{
            background: #f1f8ff;
            color: #57606a;
            padding: 8px 16px;
            font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            border-bottom: 1px solid #d0d7de;
        }}

        .diff-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            line-height: 20px;
        }}

        .diff-table tr {{
            border: none;
        }}

        /* 新增行 - 绿色背景 */
        .diff-line-add {{
            background-color: #e6ffec;
        }}

        .diff-line-add .diff-line-num {{
            background-color: #ccffd8;
            color: #24292f;
        }}

        .diff-line-add .diff-line-prefix {{
            color: #1a7f37;
        }}

        .diff-line-add .diff-line-content {{
            background-color: #e6ffec;
        }}

        /* 删除行 - 红色背景 */
        .diff-line-del {{
            background-color: #ffebe9;
        }}

        .diff-line-del .diff-line-num {{
            background-color: #ffd7d5;
            color: #24292f;
        }}

        .diff-line-del .diff-line-prefix {{
            color: #cf222e;
        }}

        .diff-line-del .diff-line-content {{
            background-color: #ffebe9;
        }}

        /* 上下文行 */
        .diff-line-ctx {{
            background-color: #ffffff;
        }}

        .diff-line-ctx .diff-line-num {{
            background-color: #f6f8fa;
            color: #57606a;
        }}

        .diff-line-ctx .diff-line-prefix {{
            color: #57606a;
        }}

        /* AI 评论标记的行号（红色） */
        .diff-line-num-marked {{
            background-color: #dc2626 !important;
            color: #ffffff !important;
            font-weight: bold;
        }}

        /* 文件头中的行号范围徽章 */
        .diff-file-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .diff-file-name {{
            font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
            font-size: 13px;
            font-weight: 600;
            color: #24292f;
        }}

        .diff-line-range-badge {{
            background: #f59e0b;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: bold;
        }}

        /* 行号列 */
        .diff-line-num {{
            width: 40px;
            min-width: 40px;
            padding: 0 8px;
            text-align: right;
            user-select: none;
            vertical-align: top;
            color: #57606a;
            border-right: 1px solid #d0d7de;
        }}

        .diff-line-num-old {{
            border-right: none;
        }}

        .diff-line-num-new {{
            border-right: 1px solid #d0d7de;
        }}

        /* 前缀列 (+/-/空格) */
        .diff-line-prefix {{
            width: 20px;
            min-width: 20px;
            padding: 0 4px;
            text-align: center;
            user-select: none;
            font-weight: bold;
        }}

        /* 代码内容列 */
        .diff-line-content {{
            padding: 0 16px 0 8px;
            white-space: pre;
            overflow-x: auto;
            color: #24292f;
        }}

        .diff-line-content pre {{
            margin: 0;
            padding: 0;
            font-family: inherit;
            font-size: inherit;
            white-space: pre;
            background: transparent;
            color: inherit;
            display: inline;
        }}

        ul {{
            margin: 10px 0;
            padding-left: 25px;
        }}

        li {{
            margin: 8px 0;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}

        .summary-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }}

        .summary-value {{
            font-size: 32px;
            font-weight: bold;
            color: #3498db;
            margin: 10px 0;
        }}

        .summary-label {{
            color: #666;
            font-size: 14px;
        }}

        .progress-bar {{
            background: #ecf0f1;
            height: 20px;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}

        .progress-fill {{
            background: #3498db;
            height: 100%;
            transition: width 0.3s ease;
        }}

        .file-change {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            border-left: 3px solid #3498db;
        }}

        .file-path {{
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 14px;
            color: #2c3e50;
            font-weight: bold;
            margin-bottom: 10px;
        }}

        .stats {{
            color: #666;
            font-size: 13px;
            margin: 5px 0;
        }}

        .stats-add {{
            color: #27ae60;
        }}

        .stats-delete {{
            color: #e74c3c;
        }}

        .priority-area {{
            background: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}

        .priority-high {{
            border-color: #e74c3c;
            background: #fff5f5;
        }}

        .priority-medium {{
            border-color: #f39c12;
            background: #fffbf0;
        }}

        .priority-low {{
            border-color: #95a5a6;
            background: #f8f9fa;
        }}

        .time-estimate {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 5px 15px;
            border-radius: 15px;
            font-size: 14px;
            margin: 10px 0;
        }}

        .confidence-score {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            margin: 10px 0;
        }}

        .confidence-high {{
            background: #d4edda;
            color: #155724;
        }}

        .confidence-medium {{
            background: #fff3cd;
            color: #856404;
        }}

        .confidence-low {{
            background: #f8d7da;
            color: #721c24;
        }}

        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #999;
            font-size: 14px;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
            .tab-buttons {{
                display: none;
            }}
            .tab-content {{
                display: block !important;
                page-break-before: always;
            }}
            .tab-content:first-of-type {{
                page-break-before: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Code Review 综合报告</h1>

        <div class="tab-container">
            <div class="tab-buttons">
                <button class="tab-button active" onclick="showTab('review')">📋 代码审查</button>
                <button class="tab-button" onclick="showTab('analyze')">🔍 变更解析</button>
                <button class="tab-button" onclick="showTab('priority')">⭐ 优先级评估</button>
            </div>
"""


def generate_combined_html_footer() -> str:
    """生成合并报告的 HTML 尾部"""
    return f"""
        </div>

        <div class="footer">
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>由 Claude Code Review Tool 生成</p>
        </div>
    </div>

    <script>
        function showTab(tabName) {{
            // 隐藏所有 tab 内容
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});

            // 移除所有按钮的 active 状态
            document.querySelectorAll('.tab-button').forEach(btn => {{
                btn.classList.remove('active');
            }});

            // 显示选中的 tab
            document.getElementById('tab-' + tabName).classList.add('active');

            // 激活对应的按钮
            event.target.classList.add('active');
        }}
    </script>
</body>
</html>
"""


def generate_analyze_content(data: Dict[str, Any], diff_content: str = None) -> str:
    """生成变更解析的内容（不含 HTML 头尾）
    
    Args:
        data: 变更解析数据
        diff_content: git diff 输出内容，用于展示代码变更
    """
    html = ""
    
    # 预解析 diff
    file_hunks = None
    if diff_content:
        file_hunks = parse_diff_to_file_hunks(diff_content)

    # 变更总览
    summary = data.get('change_summary', {})
    html += "<h2>变更总览</h2>\n"
    html += '<div class="card">\n'
    html += f'<h3>{summary.get("title", "未命名变更")}</h3>\n'

    # 类型和风险徽章
    change_type = summary.get('type', 'unknown')
    risk_level = summary.get('risk_level', 'medium')
    html += f'<p>{get_type_badge(change_type)} {get_priority_badge(risk_level)}</p>\n'

    html += f'<p><strong>变更目的:</strong> {summary.get("purpose", "未说明")}</p>\n'
    html += f'<p><strong>变更范围:</strong> {summary.get("scope", "未说明")}</p>\n'
    html += f'<p><strong>复杂度:</strong> {summary.get("estimated_complexity", "未知")}</p>\n'

    confidence = summary.get('confidence_score', data.get('confidence_score', 0))
    html += f'<p><strong>置信度:</strong> <span class="confidence-score {get_confidence_class(confidence)}">{confidence:.0%}</span></p>\n'
    html += '</div>\n'

    # 文件变更
    file_changes = data.get('file_changes', [])
    html += f"<h2>文件变更详情 ({len(file_changes)})</h2>\n"

    for change in file_changes:
        html += '<div class="file-change">\n'
        file_path = change.get("file_path", "未知文件")
        html += f'<div class="file-path">{file_path}</div>\n'
        html += f'<p><span class="badge badge-feature">{change.get("change_type", "unknown").upper()}</span></p>\n'

        lines_add = change.get('lines_added', 0)
        lines_del = change.get('lines_deleted', 0)
        html += f'<p class="stats"><span class="stats-add">+{lines_add}</span> / <span class="stats-delete">-{lines_del}</span></p>\n'

        html += f'<p><strong>目的:</strong> {change.get("purpose", "未说明")}</p>\n'

        key_changes = change.get('key_changes', [])
        if key_changes:
            html += '<p><strong>关键变更:</strong></p>\n<ul>\n'
            for kc in key_changes:
                html += f'<li>{kc}</li>\n'
            html += '</ul>\n'

        html += f'<p><strong>影响:</strong> {change.get("impact", "未说明")}</p>\n'
        
        # 添加该文件的 diff 展示
        if file_hunks:
            diff_html = get_diff_for_file(file_path, file_hunks)
            if diff_html:
                html += diff_html
        
        html += '</div>\n'

    # 架构影响
    arch_impact = data.get('architecture_impact', {})
    if arch_impact and any(arch_impact.values()):
        html += "<h2>架构影响</h2>\n"
        html += '<div class="card">\n'

        if arch_impact.get('affected_modules'):
            html += '<p><strong>受影响模块:</strong></p>\n<ul>\n'
            for module in arch_impact['affected_modules']:
                html += f'<li>{module}</li>\n'
            html += '</ul>\n'

        if arch_impact.get('new_dependencies'):
            html += '<p><strong>新增依赖:</strong></p>\n<ul>\n'
            for dep in arch_impact['new_dependencies']:
                html += f'<li>{dep}</li>\n'
            html += '</ul>\n'

        if arch_impact.get('api_changes'):
            html += '<p><strong>API 变更:</strong></p>\n<ul>\n'
            for api in arch_impact['api_changes']:
                html += f'<li>{api}</li>\n'
            html += '</ul>\n'

        html += '</div>\n'

    # 迁移注意事项
    migration_notes = data.get('migration_notes', [])
    if migration_notes:
        html += "<h2>⚠️ 迁移注意事项</h2>\n"
        html += '<div class="card">\n<ul>\n'
        for note in migration_notes:
            html += f'<li>{note}</li>\n'
        html += '</ul>\n</div>\n'

    return html


def generate_priority_content(data: Dict[str, Any], diff_content: str = None) -> str:
    """生成优先级评估的内容（不含 HTML 头尾）
    
    Args:
        data: 优先级评估数据
        diff_content: git diff 输出内容，用于展示代码变更
    """
    html = ""
    
    # 预解析 diff
    file_hunks = None
    if diff_content:
        file_hunks = parse_diff_to_file_hunks(diff_content)

    # Review 总览
    summary = data.get('review_summary', {})
    html += "<h2>Review 总览</h2>\n"

    html += '<div class="summary-grid">\n'
    html += f'''
        <div class="summary-item">
            <div class="summary-label">总文件数</div>
            <div class="summary-value">{summary.get('total_files', 0)}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">高优先级</div>
            <div class="summary-value" style="color: #e74c3c;">{summary.get('high_priority_files', 0)}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">中优先级</div>
            <div class="summary-value" style="color: #f39c12;">{summary.get('medium_priority_files', 0)}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">低优先级</div>
            <div class="summary-value" style="color: #95a5a6;">{summary.get('low_priority_files', 0)}</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">预估时长</div>
            <div class="summary-value">{summary.get('estimated_total_minutes', 0)}</div>
            <div class="summary-label">分钟</div>
        </div>
        <div class="summary-item">
            <div class="summary-label">建议 Reviewer</div>
            <div class="summary-value">{summary.get('recommended_reviewers', 1)}</div>
            <div class="summary-label">人</div>
        </div>
    '''
    html += '</div>\n'

    # 优先级区域
    priority_areas = data.get('priority_areas', [])
    html += f"<h2>重点 Review 区域 ({len(priority_areas)})</h2>\n"

    for idx, area in enumerate(priority_areas, 1):
        priority = area.get('priority', 'medium')
        html += f'<div class="priority-area priority-{priority}">\n'
        file_path = area.get("file_path", "未知文件")
        html += f'<h3>{idx}. {file_path}</h3>\n'
        html += f'<p>{get_priority_badge(priority)} '

        line_range = area.get('line_range', {})
        if line_range:
            # 处理 line_range 可能是数组或对象的情况
            if isinstance(line_range, list):
                start = line_range[0] if len(line_range) > 0 else "?"
                end = line_range[1] if len(line_range) > 1 else start
            else:
                start = line_range.get("start", "?")
                end = line_range.get("end", "?")
            html += f'<span class="code-location">行 {start} - {end}</span>'
        html += '</p>\n'

        html += f'<p><strong>原因:</strong> {area.get("reason", "未说明")}</p>\n'

        focus_points = area.get('focus_points', [])
        if focus_points:
            html += '<p><strong>关注点:</strong></p>\n<ul>\n'
            for fp in focus_points:
                html += f'<li>{fp}</li>\n'
            html += '</ul>\n'

        minutes = area.get('estimated_minutes', 0)
        html += f'<p><span class="time-estimate">⏱️ 预估 {minutes} 分钟</span></p>\n'

        risk_factors = area.get('risk_factors', [])
        if risk_factors:
            html += '<p><strong>⚠️ 风险因素:</strong></p>\n<ul>\n'
            for rf in risk_factors:
                html += f'<li>{rf}</li>\n'
            html += '</ul>\n'
        
        # 添加 diff 代码片段
        if file_hunks:
            code_loc = {
                'absolute_file_path': file_path,
                'line_range': line_range
            }
            diff_snippet_html = get_diff_snippet_for_finding(code_loc, file_hunks=file_hunks)
            if diff_snippet_html:
                html += diff_snippet_html

        html += '</div>\n'

    # Review 策略
    strategy = data.get('review_strategy', {})
    if strategy:
        html += "<h2>Review 策略</h2>\n"
        html += '<div class="card">\n'

        recommended_order = strategy.get('recommended_order', [])
        if recommended_order:
            html += '<p><strong>推荐顺序:</strong></p>\n<ol>\n'
            for order in recommended_order:
                html += f'<li>{order}</li>\n'
            html += '</ol>\n'

        prerequisites = strategy.get('prerequisites', [])
        if prerequisites:
            html += '<p><strong>前置知识:</strong></p>\n<ul>\n'
            for prereq in prerequisites:
                html += f'<li>{prereq}</li>\n'
            html += '</ul>\n'

        html += '</div>\n'

    # 时间分解
    time_breakdown = data.get('time_breakdown', {})
    if time_breakdown:
        html += "<h2>时间分解</h2>\n"
        html += '<div class="card">\n'

        total = time_breakdown.get('total', 0)
        for key, value in time_breakdown.items():
            if key != 'total' and value > 0:
                percentage = (value / total * 100) if total > 0 else 0
                label_map = {
                    'code_reading': '代码阅读',
                    'logic_verification': '逻辑验证',
                    'testing_review': '测试审查',
                    'documentation_review': '文档审查',
                    'discussion_buffer': '讨论缓冲'
                }
                label = label_map.get(key, key)
                html += f'<p><strong>{label}:</strong> {value} 分钟 ({percentage:.0f}%)</p>\n'
                html += f'<div class="progress-bar"><div class="progress-fill" style="width: {percentage}%"></div></div>\n'

        html += f'<p><strong>总计:</strong> {total} 分钟</p>\n'
        html += '</div>\n'

    # 可跳过文件
    skip_files = data.get('skip_review_files', [])
    if skip_files:
        html += "<h2>可快速浏览的文件</h2>\n"
        html += '<div class="card">\n<ul>\n'
        for sf in skip_files:
            html += f'<li><code>{sf.get("file_path", "")}</code> - {sf.get("reason", "")}</li>\n'
        html += '</ul>\n</div>\n'

    return html


def generate_review_content(data: Dict[str, Any], diff_content: str = None) -> str:
    """生成代码审查的内容（不含 HTML 头尾）
    
    Args:
        data: 审查结果数据
        diff_content: git diff 输出内容，用于展示代码变更
    """
    html = ""
    
    # 预解析 diff（避免重复解析）
    file_hunks = None
    if diff_content:
        file_hunks = parse_diff_to_file_hunks(diff_content)

    # 总体评估
    html += "<h2>总体评估</h2>\n"
    html += '<div class="card">\n'
    html += f'<p><strong>整体正确性:</strong> '
    if data.get('overall_correctness') == 'patch is correct':
        html += '<span class="badge badge-success">✓ 代码正确</span>'
    else:
        html += '<span class="badge badge-high">✗ 存在问题</span>'
    html += '</p>\n'

    html += f'<p><strong>整体说明:</strong> {data.get("overall_explanation", "无")}</p>\n'

    confidence = data.get('overall_confidence_score', 0)
    html += f'<p><strong>置信度:</strong> <span class="confidence-score {get_confidence_class(confidence)}">{confidence:.0%}</span></p>\n'
    html += '</div>\n'

    # 发现的问题
    findings = data.get('findings', [])
    html += f"<h2>发现的问题 ({len(findings)})</h2>\n"

    if not findings:
        html += '<div class="card"><p>✓ 未发现明显问题</p></div>\n'
    else:
        for idx, finding in enumerate(findings, 1):
            priority = 'medium'  # 默认优先级
            if '[P0]' in finding.get('title', '') or '[P1]' in finding.get('title', ''):
                priority = 'high'
            elif '[P3]' in finding.get('title', ''):
                priority = 'low'

            html += f'<div class="finding finding-{priority}">\n'
            html += f'<h3>{idx}. {finding.get("title", "未命名问题")}</h3>\n'
            html += f'<p>{finding.get("body", "")}</p>\n'

            # 代码位置
            code_loc = finding.get('code_location', {})
            if code_loc:
                html += '<div class="code-location">\n'
                html += f'<strong>文件:</strong> {code_loc.get("absolute_file_path", "未知")}<br>\n'
                line_range = code_loc.get('line_range', {})
                if line_range:
                    # 处理 line_range 可能是数组或对象的情况
                    if isinstance(line_range, list):
                        start = line_range[0] if len(line_range) > 0 else "?"
                        end = line_range[1] if len(line_range) > 1 else start
                    else:
                        start = line_range.get("start", "?")
                        end = line_range.get("end", "?")
                    html += f'<strong>行号:</strong> {start} - {end}\n'
                html += '</div>\n'
                
                # 添加 diff 代码片段
                if file_hunks:
                    diff_snippet_html = get_diff_snippet_for_finding(code_loc, file_hunks=file_hunks)
                    if diff_snippet_html:
                        html += diff_snippet_html

            # 置信度
            conf = finding.get('confidence_score', 0)
            html += f'<p><small>置信度: <span class="confidence-score {get_confidence_class(conf)}">{conf:.0%}</span></small></p>\n'
            html += '</div>\n'

    return html


def _ensure_dict(data: Any) -> Dict[str, Any]:
    """
    确保数据是字典类型，处理 AI 返回格式不一致的情况

    Args:
        data: 输入数据，可能是 dict、list 或其他类型

    Returns:
        字典类型的数据
    """
    if data is None:
        return {}
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        # 如果是列表，尝试取第一个元素（如果是 dict）
        if len(data) > 0 and isinstance(data[0], dict):
            return data[0]
        # 否则包装成 dict
        return {'items': data}
    # 其他类型，包装成 dict
    return {'value': data}


def generate_combined_report(
    analyze_data: Dict[str, Any] = None,
    priority_data: Dict[str, Any] = None,
    review_data: Dict[str, Any] = None,
    diff_content: str = None
) -> str:
    """
    生成合并的 HTML 报告（带 Tab 切换）

    Args:
        analyze_data: 变更解析数据
        priority_data: 优先级评估数据
        review_data: 代码审查数据
        diff_content: git diff 输出内容，用于展示代码变更

    Returns:
        合并的 HTML 报告
    """
    html = generate_combined_html_header("Code Review 综合报告")

    # 确保数据是字典类型
    review_data = _ensure_dict(review_data)
    analyze_data = _ensure_dict(analyze_data)
    priority_data = _ensure_dict(priority_data)

    # 代码审查 Tab（默认显示）
    html += '<div id="tab-review" class="tab-content active">\n'
    if review_data:
        html += generate_review_content(review_data, diff_content)
    else:
        html += '<div class="card"><p>暂无代码审查数据</p></div>\n'
    html += '</div>\n'

    # 变更解析 Tab
    html += '<div id="tab-analyze" class="tab-content">\n'
    if analyze_data:
        html += generate_analyze_content(analyze_data, diff_content)
    else:
        html += '<div class="card"><p>暂无变更解析数据</p></div>\n'
    html += '</div>\n'

    # 优先级评估 Tab
    html += '<div id="tab-priority" class="tab-content">\n'
    if priority_data:
        html += generate_priority_content(priority_data, diff_content)
    else:
        html += '<div class="card"><p>暂无优先级评估数据</p></div>\n'
    html += '</div>\n'

    html += generate_combined_html_footer()
    return html


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='将 JSON 格式的分析结果转换为 HTML 报告'
    )
    parser.add_argument('json_file', help='JSON 文件路径')
    parser.add_argument('-o', '--output', help='输出 HTML 文件路径（默认：与 JSON 同名）')
    parser.add_argument('-t', '--type',
                       choices=['review', 'analyze', 'priority', 'auto'],
                       default='auto',
                       help='报告类型（默认：自动检测）')

    args = parser.parse_args()

    try:
        # 加载 JSON 数据
        print(f"正在加载 {args.json_file}...")
        data = load_json_file(args.json_file)

        # 检测报告类型
        if args.type == 'auto':
            report_type = detect_report_type(data)
            print(f"检测到报告类型: {report_type}")
        else:
            report_type = args.type

        # 生成 HTML
        print("正在生成 HTML 报告...")
        if report_type == 'review':
            html = generate_review_report(data)
        elif report_type == 'analyze':
            html = generate_analyze_report(data)
        elif report_type == 'priority':
            html = generate_priority_report(data)
        else:
            raise Exception(f"未知的报告类型: {report_type}")

        # 确定输出文件名
        if args.output:
            output_file = args.output
        else:
            json_path = Path(args.json_file)
            output_file = json_path.with_suffix('.html')

        # 保存 HTML
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"✓ HTML 报告已生成: {output_file}")
        print(f"\n可以在浏览器中打开查看:")
        print(f"  open {output_file}")

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

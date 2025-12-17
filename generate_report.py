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

        /* 代码 diff 样式 */
        .code-diff {{
            background: #fff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            margin: 15px 0;
            overflow: hidden;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 13px;
        }}

        .diff-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }}

        .diff-line-number {{
            width: 40px;
            padding: 0 10px;
            text-align: right;
            vertical-align: top;
            color: rgba(27,31,36,0.3);
            user-select: none;
            border-right: 1px solid #d0d7de;
        }}

        .diff-line-content {{
            padding: 0 10px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        .diff-line-add {{
            background-color: #e6ffec;
        }}

        .diff-line-add .diff-line-content {{
            background-color: #ccffd8;
        }}

        .diff-line-delete {{
            background-color: #ffebe9;
        }}

        .diff-line-delete .diff-line-content {{
            background-color: #ffd7d5;
        }}

        .diff-line-context {{
            background-color: #fff;
        }}

        .diff-line-add .diff-marker {{
            color: #1a7f37;
            font-weight: bold;
        }}

        .diff-line-delete .diff-marker {{
            color: #cf222e;
            font-weight: bold;
        }}

        .diff-file-header {{
            background: #f6f8fa;
            padding: 10px 15px;
            border-bottom: 1px solid #d0d7de;
            font-weight: 600;
            color: #24292f;
        }}

        .diff-stats {{
            display: inline-block;
            margin-left: 10px;
            font-size: 12px;
            font-weight: normal;
        }}

        .diff-stats-add {{
            color: #1a7f37;
        }}

        .diff-stats-delete {{
            color: #cf222e;
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


def generate_review_report(data: Dict[str, Any]) -> str:
    """生成代码审查报告"""
    html = generate_html_header("代码审查报告")

    html += "<h1>📋 代码审查报告</h1>\n"

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
                    html += f'<strong>行号:</strong> {line_range.get("start", "?")} - {line_range.get("end", "?")}\n'
                html += '</div>\n'

            # 代码 diff 展示
            code_snippet = finding.get('code_snippet')
            if code_snippet:
                html += render_code_diff(code_snippet)

            # 置信度
            conf = finding.get('confidence_score', 0)
            html += f'<p><small>置信度: <span class="confidence-score {get_confidence_class(conf)}">{conf:.0%}</span></small></p>\n'
            html += '</div>\n'

    html += generate_html_footer()
    return html


def generate_analyze_report(data: Dict[str, Any]) -> str:
    """生成代码变更解析报告"""
    html = generate_html_header("代码变更解析报告")

    html += "<h1>🔍 代码变更解析报告</h1>\n"

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
        html += f'<div class="file-path">{change.get("file_path", "未知文件")}</div>\n'
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

        # 代码 diff 展示
        code_snippet = change.get('code_snippet')
        if code_snippet:
            html += render_code_diff(code_snippet)

        html += f'<p><strong>影响:</strong> {change.get("impact", "未说明")}</p>\n'
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


def generate_priority_report(data: Dict[str, Any]) -> str:
    """生成 Review 优先级评估报告"""
    html = generate_html_header("Review 优先级评估报告")

    html += "<h1>⭐ Review 优先级评估报告</h1>\n"

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
        html += f'<h3>{idx}. {area.get("file_path", "未知文件")}</h3>\n'
        html += f'<p>{get_priority_badge(priority)} '

        line_range = area.get('line_range', {})
        if line_range:
            html += f'<span class="code-location">行 {line_range.get("start", "?")} - {line_range.get("end", "?")}</span>'
        html += '</p>\n'

        html += f'<p><strong>原因:</strong> {area.get("reason", "未说明")}</p>\n'

        focus_points = area.get('focus_points', [])
        if focus_points:
            html += '<p><strong>关注点:</strong></p>\n<ul>\n'
            for fp in focus_points:
                html += f'<li>{fp}</li>\n'
            html += '</ul>\n'

        # 代码 diff 展示
        code_snippet = area.get('code_snippet')
        if code_snippet:
            html += render_code_diff(code_snippet)

        minutes = area.get('estimated_minutes', 0)
        html += f'<p><span class="time-estimate">⏱️ 预估 {minutes} 分钟</span></p>\n'

        risk_factors = area.get('risk_factors', [])
        if risk_factors:
            html += '<p><strong>⚠️ 风险因素:</strong></p>\n<ul>\n'
            for rf in risk_factors:
                html += f'<li>{rf}</li>\n'
            html += '</ul>\n'

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


def render_code_diff(code_snippet: Dict[str, Any]) -> str:
    """
    渲染代码 diff（GitHub 风格）

    Args:
        code_snippet: 代码片段信息，包含：
            - file_path: 文件路径（可选）
            - old_code: 旧代码（可选）
            - new_code: 新代码（可选）
            - diff: 统一 diff 格式（可选）
            - lines_added: 新增行数（可选）
            - lines_deleted: 删除行数（可选）

    Returns:
        HTML 代码 diff
    """
    if not code_snippet or not isinstance(code_snippet, dict):
        return ''

    html = '<div class="code-diff">\n'

    # 文件头
    file_path = code_snippet.get('file_path', '')
    lines_added = code_snippet.get('lines_added', 0)
    lines_deleted = code_snippet.get('lines_deleted', 0)

    if file_path or lines_added or lines_deleted:
        html += '<div class="diff-file-header">\n'
        if file_path:
            html += f'<span>{file_path}</span>\n'
        if lines_added or lines_deleted:
            html += '<span class="diff-stats">\n'
            if lines_added:
                html += f'<span class="diff-stats-add">+{lines_added}</span> '
            if lines_deleted:
                html += f'<span class="diff-stats-delete">-{lines_deleted}</span>'
            html += '</span>\n'
        html += '</div>\n'

    # 如果有统一 diff 格式，优先使用
    if 'diff' in code_snippet and code_snippet['diff']:
        html += '<table class="diff-table">\n'
        diff_lines = code_snippet['diff'].split('\n')
        old_line_num = 1
        new_line_num = 1

        for line in diff_lines:
            # 跳过 diff 头部
            if line.startswith('@@') or line.startswith('+++') or line.startswith('---') or line.startswith('diff '):
                continue

            if line.startswith('+'):
                # 新增行
                html += f'<tr class="diff-line-add">\n'
                html += f'  <td class="diff-line-number"></td>\n'
                html += f'  <td class="diff-line-number">{new_line_num}</td>\n'
                html += f'  <td class="diff-line-content"><span class="diff-marker">+</span>{line[1:]}</td>\n'
                html += '</tr>\n'
                new_line_num += 1
            elif line.startswith('-'):
                # 删除行
                html += f'<tr class="diff-line-delete">\n'
                html += f'  <td class="diff-line-number">{old_line_num}</td>\n'
                html += f'  <td class="diff-line-number"></td>\n'
                html += f'  <td class="diff-line-content"><span class="diff-marker">-</span>{line[1:]}</td>\n'
                html += '</tr>\n'
                old_line_num += 1
            else:
                # 上下文行
                html += f'<tr class="diff-line-context">\n'
                html += f'  <td class="diff-line-number">{old_line_num}</td>\n'
                html += f'  <td class="diff-line-number">{new_line_num}</td>\n'
                html += f'  <td class="diff-line-content">{line}</td>\n'
                html += '</tr>\n'
                old_line_num += 1
                new_line_num += 1

        html += '</table>\n'

    # 否则使用 old_code 和 new_code 对比
    elif 'old_code' in code_snippet or 'new_code' in code_snippet:
        html += '<table class="diff-table">\n'

        old_code = code_snippet.get('old_code', '').split('\n') if code_snippet.get('old_code') else []
        new_code = code_snippet.get('new_code', '').split('\n') if code_snippet.get('new_code') else []

        # 显示删除的行
        for i, line in enumerate(old_code, 1):
            html += f'<tr class="diff-line-delete">\n'
            html += f'  <td class="diff-line-number">{i}</td>\n'
            html += f'  <td class="diff-line-number"></td>\n'
            html += f'  <td class="diff-line-content"><span class="diff-marker">-</span>{line}</td>\n'
            html += '</tr>\n'

        # 显示新增的行
        for i, line in enumerate(new_code, 1):
            html += f'<tr class="diff-line-add">\n'
            html += f'  <td class="diff-line-number"></td>\n'
            html += f'  <td class="diff-line-number">{i}</td>\n'
            html += f'  <td class="diff-line-content"><span class="diff-marker">+</span>{line}</td>\n'
            html += '</tr>\n'

        html += '</table>\n'

    html += '</div>\n'
    return html


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

        /* 代码 diff 样式 */
        .code-diff {{
            background: #fff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            margin: 15px 0;
            overflow: hidden;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 13px;
        }}

        .diff-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }}

        .diff-line-number {{
            width: 40px;
            padding: 0 10px;
            text-align: right;
            vertical-align: top;
            color: rgba(27,31,36,0.3);
            user-select: none;
            border-right: 1px solid #d0d7de;
        }}

        .diff-line-content {{
            padding: 0 10px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        .diff-line-add {{
            background-color: #e6ffec;
        }}

        .diff-line-add .diff-line-content {{
            background-color: #ccffd8;
        }}

        .diff-line-delete {{
            background-color: #ffebe9;
        }}

        .diff-line-delete .diff-line-content {{
            background-color: #ffd7d5;
        }}

        .diff-line-context {{
            background-color: #fff;
        }}

        .diff-line-add .diff-marker {{
            color: #1a7f37;
            font-weight: bold;
        }}

        .diff-line-delete .diff-marker {{
            color: #cf222e;
            font-weight: bold;
        }}

        .diff-file-header {{
            background: #f6f8fa;
            padding: 10px 15px;
            border-bottom: 1px solid #d0d7de;
            font-weight: 600;
            color: #24292f;
        }}

        .diff-stats {{
            display: inline-block;
            margin-left: 10px;
            font-size: 12px;
            font-weight: normal;
        }}

        .diff-stats-add {{
            color: #1a7f37;
        }}

        .diff-stats-delete {{
            color: #cf222e;
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


def generate_analyze_content(data: Dict[str, Any]) -> str:
    """生成变更解析的内容（不含 HTML 头尾）"""
    html = ""

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
        html += f'<div class="file-path">{change.get("file_path", "未知文件")}</div>\n'
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

        # 代码 diff 展示
        code_snippet = change.get('code_snippet')
        if code_snippet:
            html += render_code_diff(code_snippet)

        html += f'<p><strong>影响:</strong> {change.get("impact", "未说明")}</p>\n'
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


def generate_priority_content(data: Dict[str, Any]) -> str:
    """生成优先级评估的内容（不含 HTML 头尾）"""
    html = ""

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
        html += f'<h3>{idx}. {area.get("file_path", "未知文件")}</h3>\n'
        html += f'<p>{get_priority_badge(priority)} '

        line_range = area.get('line_range', {})
        if line_range:
            html += f'<span class="code-location">行 {line_range.get("start", "?")} - {line_range.get("end", "?")}</span>'
        html += '</p>\n'

        html += f'<p><strong>原因:</strong> {area.get("reason", "未说明")}</p>\n'

        focus_points = area.get('focus_points', [])
        if focus_points:
            html += '<p><strong>关注点:</strong></p>\n<ul>\n'
            for fp in focus_points:
                html += f'<li>{fp}</li>\n'
            html += '</ul>\n'

        # 代码 diff 展示
        code_snippet = area.get('code_snippet')
        if code_snippet:
            html += render_code_diff(code_snippet)

        minutes = area.get('estimated_minutes', 0)
        html += f'<p><span class="time-estimate">⏱️ 预估 {minutes} 分钟</span></p>\n'

        risk_factors = area.get('risk_factors', [])
        if risk_factors:
            html += '<p><strong>⚠️ 风险因素:</strong></p>\n<ul>\n'
            for rf in risk_factors:
                html += f'<li>{rf}</li>\n'
            html += '</ul>\n'

        html += '</div>\n'

    # Review 策略
    strategy = data.get('review_strategy', )
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


def generate_review_content(data: Dict[str, Any]) -> str:
    """生成代码审查的内容（不含 HTML 头尾）"""
    html = ""

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
                    html += f'<strong>行号:</strong> {line_range.get("start", "?")} - {line_range.get("end", "?")}\n'
                html += '</div>\n'

            # 代码 diff 展示
            code_snippet = finding.get('code_snippet')
            if code_snippet:
                html += render_code_diff(code_snippet)

            # 置信度
            conf = finding.get('confidence_score', 0)
            html += f'<p><small>置信度: <span class="confidence-score {get_confidence_class(conf)}">{conf:.0%}</span></small></p>\n'
            html += '</div>\n'

    return html


def generate_combined_report(
    analyze_data: Dict[str, Any] = None,
    priority_data: Dict[str, Any] = None,
    review_data: Dict[str, Any] = None
) -> str:
    """
    生成合并的 HTML 报告（带 Tab 切换）

    Args:
        analyze_data: 变更解析数据
        priority_data: 优先级评估数据
        review_data: 代码审查数据

    Returns:
        合并的 HTML 报告
    """
    html = generate_combined_html_header("Code Review 综合报告")

    # 代码审查 Tab（默认显示）
    html += '<div id="tab-review" class="tab-content active">\n'
    if review_data:
        html += generate_review_content(review_data["structured_output"])
    else:
        html += '<div class="card"><p>暂无代码审查数据</p></div>\n'
    html += '</div>\n'

    # 变更解析 Tab
    html += '<div id="tab-analyze" class="tab-content">\n'
    if analyze_data:
        html += generate_analyze_content(analyze_data["structured_output"])
    else:
        html += '<div class="card"><p>暂无变更解析数据</p></div>\n'
    html += '</div>\n'

    # 优先级评估 Tab
    html += '<div id="tab-priority" class="tab-content">\n'
    if priority_data:
        html += generate_priority_content(priority_data["structured_output"])
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

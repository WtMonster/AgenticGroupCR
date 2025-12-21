"""
JSON 处理工具模块
提供 JSON 提取、验证、格式化等功能
"""

import json
import re
from typing import Optional, Dict, Any


def extract_first_json_object(text: str) -> Optional[str]:
    """
    从文本中提取第一个完整的 JSON 对象字符串

    处理 Codex 等工具可能输出重复 JSON 的情况（如 }{  拼接）

    Args:
        text: 包含 JSON 的文本

    Returns:
        第一个完整的 JSON 对象字符串，如果未找到则返回 None
    """
    brace_count = 0
    start_idx = -1
    in_string = False
    escape_next = False

    for i, char in enumerate(text):
        # 处理字符串内的转义
        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        # 处理字符串边界
        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        # 只在字符串外部计算括号
        if not in_string:
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    return text[start_idx:i+1]

    return None


def extract_json_from_text(text: str, mode: str = None) -> Optional[Dict[str, Any]]:
    """
    从文本中提取 JSON 对象

    支持三种模式的 JSON 提取：
    - review: 包含 findings, overall_correctness 等字段
    - analyze: 包含 change_summary, file_changes 等字段
    - priority: 包含 review_summary, priority_areas 等字段

    Args:
        text: 包含 JSON 的文本
        mode: 模式（review/analyze/priority），用于优先匹配特定格式

    Returns:
        提取的 JSON 对象，如果提取失败则返回 None
    """
    # 定义各模式的特征字段
    mode_signatures = {
        'review': ['findings', 'overall_correctness'],
        'analyze': ['change_summary', 'file_changes'],
        'priority': ['review_summary', 'priority_areas']
    }

    def matches_mode(parsed: dict, target_mode: str) -> bool:
        """检查解析的 JSON 是否匹配指定模式"""
        if target_mode not in mode_signatures:
            return True
        sig_fields = mode_signatures[target_mode]
        return all(field in parsed for field in sig_fields)

    # 尝试直接解析整个文本
    try:
        parsed = json.loads(text)
        if mode is None or matches_mode(parsed, mode):
            return parsed
    except json.JSONDecodeError:
        pass

    # 尝试查找 JSON 代码块（```json ... ```）
    # 如果指定了 mode，需要找到匹配的代码块
    json_block_pattern = r'```json\s*\n?(.*?)\n?```'
    matches = re.findall(json_block_pattern, text, re.DOTALL)
    for match in matches:
        try:
            parsed = json.loads(match)
            if mode is None or matches_mode(parsed, mode):
                return parsed
        except json.JSONDecodeError:
            continue

    # 如果指定了模式，优先查找特定模式的 JSON
    if mode and mode in mode_signatures:
        sig_fields = mode_signatures[mode]
        first_field = sig_fields[0]

        # 查找以特定字段开头的 JSON（可能有多个，需要遍历）
        search_start = 0
        while True:
            # 查找下一个可能的起始位置
            pos1 = text.find(f'"{first_field}"', search_start)
            if pos1 == -1:
                break
            
            # 向前找到 JSON 对象的开始 {
            brace_start = text.rfind('{', search_start, pos1)
            if brace_start == -1:
                search_start = pos1 + 1
                continue
            
            json_str = extract_first_json_object(text[brace_start:])
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    if matches_mode(parsed, mode):
                        return parsed
                except json.JSONDecodeError:
                    pass
            
            search_start = pos1 + 1

    # 尝试提取所有完整的 JSON 对象，找到匹配的
    brace_count = 0
    start_idx = -1

    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                try:
                    json_str = text[start_idx:i+1]
                    parsed = json.loads(json_str)
                    
                    # 如果指定了模式，检查是否匹配
                    if mode:
                        if matches_mode(parsed, mode):
                            return parsed
                        # 不匹配，继续查找下一个
                    else:
                        # 未指定模式，检查是否匹配任意已知模式
                        for sig_fields in mode_signatures.values():
                            if all(field in parsed for field in sig_fields):
                                return parsed
                        # 如果不匹配任何已知模式但是有效 JSON，也返回
                        if isinstance(parsed, dict):
                            return parsed
                except json.JSONDecodeError:
                    pass
                # 重置，继续查找下一个
                start_idx = -1

    return None


def validate_review_schema(data: Dict[str, Any]) -> bool:
    """
    验证 review 结果是否符合 schema

    Args:
        data: 待验证的 JSON 数据

    Returns:
        是否符合 schema
    """
    # 检查必需字段
    required_fields = ['findings', 'overall_correctness', 'overall_explanation', 'overall_confidence_score']
    for field in required_fields:
        if field not in data:
            print(f"警告: 缺少必需字段 '{field}'")
            return False

    # 检查 findings 是否为列表
    if not isinstance(data['findings'], list):
        print("警告: 'findings' 必须是列表")
        return False

    # 检查每个 finding 的结构
    for idx, finding in enumerate(data['findings']):
        required_finding_fields = ['title', 'body', 'confidence_score', 'code_location']
        for field in required_finding_fields:
            if field not in finding:
                print(f"警告: findings[{idx}] 缺少必需字段 '{field}'")
                return False

        # 检查 code_location 结构
        if 'absolute_file_path' not in finding['code_location']:
            print(f"警告: findings[{idx}].code_location 缺少 'absolute_file_path'")
            return False
        if 'line_range' not in finding['code_location']:
            print(f"警告: findings[{idx}].code_location 缺少 'line_range'")
            return False

    # 检查 overall_correctness 的值
    valid_correctness = ['patch is correct', 'patch is incorrect']
    if data['overall_correctness'] not in valid_correctness:
        print(f"警告: 'overall_correctness' 必须是 {valid_correctness} 之一")
        return False

    return True


def create_fallback_review(error_msg: str) -> Dict[str, Any]:
    """
    创建一个后备的 review 结果

    Args:
        error_msg: 错误信息

    Returns:
        后备的 review 结果
    """
    return {
        "findings": [],
        "overall_correctness": "patch is correct",
        "overall_explanation": f"Review 解析失败: {error_msg}。请查看原始输出文件。",
        "overall_confidence_score": 0.0
    }


def format_json(data: Dict[str, Any], indent: int = 2) -> str:
    """
    格式化 JSON 数据

    Args:
        data: JSON 数据
        indent: 缩进空格数

    Returns:
        格式化后的 JSON 字符串
    """
    return json.dumps(data, ensure_ascii=False, indent=indent)


def parse_json_file(file_path: str) -> Dict[str, Any]:
    """
    从文件中解析 JSON

    Args:
        file_path: JSON 文件路径

    Returns:
        解析后的 JSON 对象

    Raises:
        Exception: 文件读取或解析失败
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise Exception(f"解析 JSON 文件失败: {e}")


def save_json_file(data: Dict[str, Any], file_path: str, indent: int = 2) -> None:
    """
    保存 JSON 到文件

    Args:
        data: JSON 数据
        file_path: 保存路径
        indent: 缩进空格数

    Raises:
        Exception: 文件写入失败
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
    except Exception as e:
        raise Exception(f"保存 JSON 文件失败: {e}")

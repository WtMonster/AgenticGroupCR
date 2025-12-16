"""
JSON 处理工具模块
提供 JSON 提取、验证、格式化等功能
"""

import json
import re
from typing import Optional, Dict, Any


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    从文本中提取 JSON 对象

    Args:
        text: 包含 JSON 的文本

    Returns:
        提取的 JSON 对象，如果提取失败则返回 None
    """
    # 尝试直接解析整个文本
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试查找 JSON 代码块（```json ... ```）
    json_block_pattern = r'```json\s*\n?(.*?)\n?```'
    matches = re.findall(json_block_pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass

    # 优先查找包含 "findings" 的 JSON 对象（这是我们期望的 review 结果格式）
    # 查找 {"findings": 开头的 JSON
    findings_pattern = r'\{"findings":\s*\[.*?\].*?"overall_correctness".*?"overall_explanation".*?"overall_confidence_score".*?\}'
    matches = re.findall(findings_pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass

    # 尝试查找包含 "findings" 的完整 JSON 对象
    findings_start = text.find('{"findings"')
    if findings_start == -1:
        findings_start = text.find('{ "findings"')

    if findings_start != -1:
        brace_count = 0
        for i in range(findings_start, len(text)):
            char = text[i]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    try:
                        json_str = text[findings_start:i+1]
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        break

    # 最后尝试查找任意完整的 JSON 对象 { ... }
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
                    # 验证是否是我们期望的 review 结果
                    if 'findings' in parsed:
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

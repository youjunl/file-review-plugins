from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

import ast
import re
import json
from dataclasses import dataclass

@dataclass
class HeadingNode:
    text: str
    paragraph_no: int
    level: int
    children: list["HeadingNode"]
    text_list: list[str]


def dict_to_heading_node(data: dict) -> HeadingNode:
    """递归将字典转换为 HeadingNode 对象"""
    return HeadingNode(
        text=data['text'],
        paragraph_no=data['paragraph_no'],
        level=data['level'],
        children=[dict_to_heading_node(child) for child in data['children']],
        text_list=data['text_list']
    )
    

def extract_dicts_from_string(input_string):
    # 定义正则表达式模式来匹配字典
    pattern = r'\{[\s\S]*?"position":\s*".*?"[\s\S]*?"suggestion":\s*".*?"[\s\S]*?\}'

    # 使用正则表达式查找所有匹配的字典字符串
    matches = re.findall(pattern, input_string, re.DOTALL)

    # 将匹配的字符串转换为字典对象
    dicts = []
    for match in matches:
        try:
            # 使用 ast.literal_eval 将字符串安全地转换为字典
            dict_obj = ast.literal_eval(match)
            dicts.append(dict_obj)
        except (ValueError, SyntaxError):
            # 如果转换失败，跳过这个匹配项
            continue

    return dicts


def remove_sequence_number(text: str) -> str:
    return re.sub(r'^\d+(\.\d+)*\s*', '', text)


def find_nodes_by_text(nodes: list[HeadingNode], search_text: str, threshold: int = 90) -> list[HeadingNode]:

    matching_nodes = []
    cleaned_search_text = remove_sequence_number(search_text)

    def traverse(node: HeadingNode):
        cleaned_node_text = remove_sequence_number(node.text)
        # if fuzz.partial_ratio(cleaned_search_text, cleaned_node_text) >= threshold:
        if cleaned_search_text in cleaned_node_text:
            matching_nodes.append(node)

        # Recursively search through children
        for child in node.children:
            if isinstance(child, HeadingNode):
                traverse(child)

    # Process each root node
    for node in nodes:
        traverse(node)

    return matching_nodes

def remove_think_section(text):
    """
    移除文本中<think>...</think>标签及其包含的内容
    """
    pattern = r'<think>.*?</think>\s*'
    return re.sub(pattern, '', text, flags=re.DOTALL)


class PostProcessTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        scheme_json = tool_parameters.get("scheme_json")
        llm_result = tool_parameters.get("llm_result")
        reference = tool_parameters.get("reference")
        level = tool_parameters.get("level")
        
        scheme_json = remove_think_section(scheme_json)
        parsed_data = json.loads(scheme_json)
        scheme_tree = [dict_to_heading_node(item) for item in parsed_data]
        result_list = extract_dicts_from_string(llm_result)

        for data in result_list:
            data["reference"] = reference
            data["level"] =  level
            result_nodes = find_nodes_by_text(scheme_tree, data["position"])
            if result_nodes:
                data["paragraph_no"] = result_nodes[0].paragraph_no
            else:
                data["paragraph_no"] = 1

        yield self.create_variable_message("result", result_list)
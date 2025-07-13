from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

import ast
import re
import json
from dataclasses import dataclass
from typing import Any
from difflib import SequenceMatcher


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


def remove_sequence_number(text: str) -> str:
    return re.sub(r'^\d+(\.\d+)*\s*', '', text)


def find_nodes_by_text(nodes: list[HeadingNode], search_text: str, threshold: int = 30) -> list[HeadingNode]:
    cleaned_search = remove_sequence_number(search_text)
    exact_nodes = []

    # 精确匹配遍历函数
    def exact_traverse(node: HeadingNode):
        cleaned_node = remove_sequence_number(node.text)
        if cleaned_node == cleaned_search:
            exact_nodes.append(node)
        for child in node.children:
            if isinstance(child, HeadingNode):
                exact_traverse(child)

    # 先执行精确匹配
    for node in nodes:
        exact_traverse(node)
    
    if exact_nodes:
        return exact_nodes

    # 精确匹配无结果时执行模糊匹配
    fuzzy_nodes = []

    def fuzzy_traverse(node: HeadingNode):
        cleaned_node = remove_sequence_number(node.text)
        similarity = SequenceMatcher(None, cleaned_search, cleaned_node).ratio() * 100
        if similarity >= threshold:
            fuzzy_nodes.append(node)
        for child in node.children:
            if isinstance(child, HeadingNode):
                fuzzy_traverse(child)

    for node in nodes:
        fuzzy_traverse(node)

    return fuzzy_nodes

def extract_text(node: HeadingNode) -> str:
    # 标题
    result = node.text + '\n'
    # 将 text_list 中的内容合并成一个字符串
    result += '\n'.join(node.text_list)
    # 遍历 children，递归调用 to_str 来拼接它们的内容
    for child in node.children:
        result += '\n' + extract_text(child)  # 递归拼接子节点内容
    return result

class DocxFindTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        keyword = tool_parameters.get("keyword")
        scheme_json = tool_parameters.get("scheme_json")
        target = keyword
        parsed_data = json.loads(scheme_json)
        scheme_heading_tree = [dict_to_heading_node(item) for item in parsed_data]
        
        scheme_nodes = find_nodes_by_text(scheme_heading_tree, target)

        if scheme_nodes:
            scheme_text = extract_text(scheme_nodes[0])
        else:
            scheme_text = ''
        yield self.create_variable_message("scheme_text",scheme_text)

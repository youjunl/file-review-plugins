from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

import docx
import httpx
import re
from io import BytesIO
from dataclasses import dataclass,asdict, is_dataclass
import json
from typing import Any

@dataclass
class HeadingNode:
    text: str
    paragraph_no: int
    level: int
    children: list["HeadingNode"]
    text_list: list[str]

def table_to_markdown(table_data: list[list[str]]) -> str:
    """将二维表格数据转换为markdown格式"""
    if not table_data:
        return ""
    
    # 处理表头分隔线
    headers = table_data[0]
    separators = ["---"] * len(headers)
    
    # 构建markdown行
    markdown_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separators) + " |"
    ]
    
    # 添加数据行
    for row in table_data[1:]:
        markdown_lines.append("| " + " | ".join(row) + " |")
    
    # 处理空单元格
    markdown = "\n".join(markdown_lines).replace("  ", " ")
    return markdown + "\n"  # 添加换行保证格式

def dataclass_to_dict(obj: Any) -> Any:
    """递归处理 dataclass 对象和嵌套结构"""
    if is_dataclass(obj):
        return {k: dataclass_to_dict(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    return obj


def clean_text(text: str) -> str:
    """
    去掉文本中的 \t 和后面的数字
    """
    return re.sub(r"\t\d+", "", text).strip()

def get_heading_level(text: str, style_name: str | None = None) -> int:
    """
    根据标题文本和样式名称判断标题级别
    :param text: 标题文本
    :param style_name: 段落的样式名称
    :return: 标题级别，1为一级标题，2为二级标题，以此类推
    """
    text = clean_text(text)

    # 如果是样式名称是目录样式，直接跳过
    if style_name and style_name.startswith("toc"):
        return 0

    # 如果样式名称是标准的 Heading 1-4，直接根据样式名称判断级别
    if style_name and style_name.startswith("Heading"):
        try:
            level = int(style_name.replace("Heading ", ""))
            return level
        except ValueError:
            pass  # 如果样式名称不是标准的 Heading 1-4，继续使用文本匹配

    # 排除包含数学表达式或单位的内容
    if re.search(r"[+\-*/=]", text) or re.search(r"[A-Za-z]{2,}", text):
        return 0

    # 匹配 "第xx章 xxx" 格式的标题
    chapter_match = re.match(r"第([零一二三四五六七八九十百千万\d]+)章", text)
    if chapter_match:
        return 1  # 一级标题

    # 匹配 "x.x" 或 "x.x.x" 或 "x.x.x.x" 格式的标题
    section_match = re.match(r"(\d+)(\.\d+)+", text)
    if section_match:
        # 根据点的数量判断级别
        return len(section_match.group(0).split("."))

    # 匹配附录标题
    if text.startswith("附录"):
        # 匹配 "附录" 或 "附录A" 或 "附录 A" 等格式
        appendix_match = re.match(
            r"^附录[\s　]*([A-Za-z\d零一二三四五六七八九十百千万]*)$", text.strip()
        )
        if appendix_match:
            if appendix_match.group(1):  # 带字母、数字或中文序号
                return 2
            else:  # 不带字母、数字或中文序号
                return 1
        return 0  # 如果不是附录标题，返回0

    # 匹配附件标题
    if text.startswith("附件"):
        # 匹配 "附件" 或 "附件A" 或 "附件 A" 等格式
        attachment_match = re.match(
            r"^附件[\s　]*([A-Za-z\d零一二三四五六七八九十百千万]*)$", text.strip()
        )
        if attachment_match:
            if attachment_match.group(1):  # 带字母、数字或中文序号
                return 2
            else:  # 不带字母、数字或中文序号
                return 1
        return 0  # 如果不是附件标题，返回0

    # 匹配附表标题
    if text.startswith("附表"):
        # 匹配 "附表" 或 "附表A" 或 "附表 A" 等格式
        attachment_match = re.match(
            r"^附表[\s　]*([A-Za-z\d零一二三四五六七八九十百千万]*)$", text.strip()
        )
        if attachment_match:
            if attachment_match.group(1):  # 带字母、数字或中文序号
                return 2
            else:  # 不带字母、数字或中文序号
                return 1
        return 0  # 如果不是附表标题，返回0

    return 0  # 不是标题

    
def build_heading_tree_new(doc) -> list[HeadingNode]:
    root_nodes: list[HeadingNode] = []
    current_path: list[HeadingNode] = []
    para_index = -1

    for element in doc.element.body.iterchildren():
        tag = element.tag.split("}")[-1]

        if tag == "p":
            para_index += 1
            paragraph = docx.text.paragraph.Paragraph(element, doc)
            text = clean_text(paragraph.text)
            if not text:
                continue

            style_name = paragraph.style.name if paragraph.style else None
            level = get_heading_level(text, style_name)

            if level > 0:
                new_node = HeadingNode(
                    text=text,
                    paragraph_no=para_index,
                    level=level,
                    children=[],
                    text_list=[],
                )

                if level == 1:
                    root_nodes.append(new_node)
                    current_path = [new_node]
                else:
                    while current_path and current_path[-1].level >= level:
                        current_path.pop()
                    if current_path:
                        current_path[-1].children.append(new_node)
                        current_path.append(new_node)
            else:
                if current_path:
                    current_path[-1].text_list.append(text)

        elif tag == "tbl":
            # 提取表格数据
            table = docx.table.Table(element, doc)
            table_data = []
            for row in table.rows:
                row_data = [clean_text(cell.text) for cell in row.cells]
                table_data.append(row_data)
            
            # 转换为markdown并插入到当前节点的text_list
            markdown_table = table_to_markdown(table_data)
            if current_path:
                current_path[-1].text_list.append(markdown_table)
            else:
                # 处理文档开头的独立表格
                virtual_node = HeadingNode(
                    text="[表格]",
                    paragraph_no=-1,
                    level=0,
                    children=[],
                    text_list=[markdown_table],
                )
                root_nodes.append(virtual_node)

    return root_nodes

class DocxSplitTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        url = tool_parameters.get("url")
        try:
            response = httpx.get(url)
            response.raise_for_status()
            doc_stream = BytesIO(response.content)
            doc_stream.seek(0)
            scheme_doc = docx.Document(doc_stream)

            scheme_heading_tree = build_heading_tree_new(scheme_doc)

            scheme_json = json.dumps(
                dataclass_to_dict(scheme_heading_tree), 
                ensure_ascii=False 
            )
            yield self.create_json_message(
                {
                    "schemeJson": scheme_json
                }
            )
        except Exception as e:
            yield self.create_json_message({
                "error": f" {str(e)}"
            })

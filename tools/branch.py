from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class BranchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        key = tool_parameters.get("key")
        requirements = tool_parameters.get("requirements")
        levels = tool_parameters.get("levels")
        levels = levels.split(',')
        try:
            activated = False
            level = ""
            if key in requirements:
                activated = True
                requirements = requirements.split(',')
                for i, r in enumerate(requirements):
                    if key in r:
                        level = levels[i]
                        break
            yield self.create_json_message(
                    {
                        "activated": activated,
                        "level":level
                    }
                )
        except Exception as e:
            yield self.create_json_message({
                "error": f" {str(e)}"
            })

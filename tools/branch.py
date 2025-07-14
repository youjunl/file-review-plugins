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
        activated = "0"
        level = ""
        if key in requirements:
            activated = "1"
            requirements = requirements.split(',')
            for i, r in enumerate(requirements):
                if key in r:
                    level = levels[i]
                    break
        yield self.create_variable_message("activated", activated)
        yield self.create_variable_message("level", level)

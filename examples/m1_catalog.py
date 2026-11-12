"""M1 owner demonstration of internal catalog/contracts, not an MCP host tool call."""

import json

from best_practices_mcp.criteria import get_criteria
from best_practices_mcp.errors import DomainError
from best_practices_mcp.sdk_adapter import tool_result


def main() -> None:
    result = get_criteria("passing", ["description_good"])
    print("Offline catalog core (not yet registered as an MCP tool):")
    print(json.dumps(tool_result("get_criteria", result).structured_content, indent=2))
    try:
        get_criteria("passing", ["not_a_criterion"])
    except DomainError as error:
        print("Expected invalid-criterion example:")
        print(
            json.dumps(tool_result("get_criteria", error.to_payload()).structured_content, indent=2)
        )


if __name__ == "__main__":
    main()

from llmc_mcp.server import TOOLS


def test_all_tool_parameters_have_descriptions():
    """
    Validates that every parameter in every tool's inputSchema has a description.
    """
    missing_descriptions = []

    for tool in TOOLS:
        schema = tool.inputSchema
        if "properties" in schema:
            for param, definition in schema["properties"].items():
                if "description" not in definition or not definition["description"]:
                    missing_descriptions.append(f"{tool.name}.{param}")

    assert not missing_descriptions, (
        "The following tool parameters are missing a 'description' field:\n"
        + "\n".join(missing_descriptions)
    )

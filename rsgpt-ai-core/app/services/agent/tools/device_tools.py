"""Device tool factory for converting device JSON tools to FunctionTool objects"""

import copy
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

from agents import Agent, FunctionTool, RunContextWrapper

from app.services.streaming import connection_manager

logger = logging.getLogger(__name__)


def _fix_json_schema(schema: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    """
    Fix common JSON schema issues from device tools to ensure OpenAI API compatibility.

    Common issues:
    - Missing 'type' key in properties
    - Invalid type values
    - Missing required keys

    Args:
        schema: The JSON schema to fix
        tool_name: Tool name for logging

    Returns:
        Fixed JSON schema (deep copy to avoid mutating original)
    """
    if not isinstance(schema, dict):
        logger.warning(
            f"Tool {tool_name}: Schema is not a dict, returning empty object schema"
        )
        return {"type": "object", "properties": {}}

    # Make a deep copy to avoid mutating the original schema
    schema = copy.deepcopy(schema)

    # Ensure top-level schema has 'type'
    if "type" not in schema:
        logger.warning(f"Tool {tool_name}: Adding missing 'type' to schema")
        schema["type"] = "object"

    # Fix properties if they exist
    if "properties" in schema and isinstance(schema["properties"], dict):
        for prop_name, prop_schema in schema["properties"].items():
            if isinstance(prop_schema, dict):
                # Ensure each property has a 'type'
                if "type" not in prop_schema:
                    # Try to infer type from other fields
                    if "enum" in prop_schema:
                        prop_schema["type"] = "string"
                        logger.warning(
                            f"Tool {tool_name}: Inferred type 'string' for "
                            f"property '{prop_name}' (has enum)"
                        )
                    elif "properties" in prop_schema:
                        prop_schema["type"] = "object"
                        logger.warning(
                            f"Tool {tool_name}: Inferred type 'object' for "
                            f"property '{prop_name}' (has properties)"
                        )
                    elif "items" in prop_schema:
                        prop_schema["type"] = "array"
                        logger.warning(
                            f"Tool {tool_name}: Inferred type 'array' for "
                            f"property '{prop_name}' (has items)"
                        )
                    else:
                        # Default to string if we can't infer
                        prop_schema["type"] = "string"
                        logger.warning(
                            f"Tool {tool_name}: Defaulting to type 'string' for "
                            f"property '{prop_name}' (no type specified)"
                        )

                # Recursively fix nested objects
                if prop_schema.get("type") == "object" and "properties" in prop_schema:
                    prop_schema.update(
                        _fix_json_schema(prop_schema, f"{tool_name}.{prop_name}")
                    )

                # Fix array items
                if prop_schema.get("type") == "array" and "items" in prop_schema:
                    if isinstance(prop_schema["items"], dict):
                        prop_schema["items"] = _fix_json_schema(
                            prop_schema["items"], f"{tool_name}.{prop_name}[]"
                        )

    return schema


def parse_device_tools_to_functions(
    device_id: str,
    json_tools: List[Dict[str, Any]],
    agent_ref: Optional[Agent],
    update_callback: Optional[Callable[[Agent, str], Awaitable[None]]],
) -> List[Any]:
    """
    Convert device JSON tool definitions into Agent SDK FunctionTool objects.

    Input Format (from device list_tools response):
        Device returns: {"tools": [...], "device_id": "...", "count": N}

        Each tool in the array has:
        {
            "name": "read_file",
            "description": "Read the contents of a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["path"]
            }
        }

    Output Format:
        Agent SDK FunctionTool objects:
        FunctionTool(
            name="read_file",
            description="Read the contents of a file",
            params_json_schema={
                "type": "object",
                "properties": {...},
                "required": [...]
            },
            on_invoke_tool=handler_function
        )

    Each created tool handler will:
    1. Accept parameters via RunContextWrapper and args string
    2. Route execution to device via WebSocket
    3. Always call update_callback to refresh agent.tools after execution
    4. Return the device's response as JSON

    Args:
        device_id: Device that owns these tools
        json_tools: List of tool definitions with "input_schema"
        agent_ref: Reference to the agent (for updating agent.tools)
        update_callback: Function to call when tools need updating

    Returns:
        List of FunctionTool objects ready for Agent SDK
    """
    tool_objects = []
    seen_names = set()  # Track tool names to deduplicate

    for json_tool in json_tools:
        # Parse tool definition from device
        # Expected format: {"name": "...", "description": "...", "input_schema": {...}}
        if "name" in json_tool and "input_schema" in json_tool:
            tool_name = json_tool.get("name")
            tool_desc = json_tool.get("description", "")
            tool_params = json_tool.get("input_schema", {})
        else:
            logger.warning(
                f"Skipping tool with invalid format (missing 'name' or 'input_schema'): {json_tool}"
            )
            continue

        if not tool_name:
            logger.warning(f"Skipping tool without name: {json_tool}")
            continue

        # Skip duplicate tool names (tool names must be unique)
        if tool_name in seen_names:
            logger.warning(
                f"Skipping duplicate tool '{tool_name}' from device {device_id}. "
                f"Tool names must be unique."
            )
            continue
        seen_names.add(tool_name)

        # Fix the schema to ensure OpenAI API compatibility
        tool_params = _fix_json_schema(tool_params, tool_name)

        # Create a handler for this specific tool using closure
        def make_handler(
            name: str, dev_id: str, agent: Optional[Agent], updater: Optional[Callable]
        ):
            """Create a tool handler with captured variables via closure"""

            async def handler(ctx: RunContextWrapper[Any], args: str) -> str:
                """
                Tool wrapper that:
                1. Executes tool via WebSocket
                2. Always updates agent.tools after execution (if agent and callback provided)
                3. Returns result

                Args:
                    ctx: Run context wrapper from the agent SDK
                    args: Parameters for the tool as a JSON string
                """
                try:
                    # Parse tool arguments from JSON string
                    try:
                        args_dict = json.loads(args) if args else {}
                    except json.JSONDecodeError:
                        args_dict = {}

                    # Check if device is still connected
                    if not connection_manager.is_device_connected(dev_id):
                        logger.warning(f"Device {dev_id} not connected for tool {name}")
                        return json.dumps(
                            {
                                "result": None,
                                "error": f"Device '{dev_id}' is not connected",
                                "tool_name": name,
                            }
                        )

                    # Execute tool via WebSocket
                    logger.info(
                        f"Executing tool '{name}' on device '{dev_id}' "
                        f"with arguments: {args_dict}"
                    )

                    response = await connection_manager.request_invoke_tool(
                        dev_id,
                        name,
                        args_dict,
                        timeout=1800.0,  # 30 minutes for slow RS2 operations
                    )

                    # Always update tools after tool execution (if callback and agent provided)
                    if updater and agent:
                        logger.info(
                            f"Updating tools for device {dev_id} after executing {name}"
                        )
                        try:
                            # Type assertions to help type checker understand non-None values
                            updater_func = cast(Callable[[Agent, str], Any], updater)
                            agent_obj = cast(Agent, agent)
                            # Trigger tool refresh
                            await updater_func(agent_obj, dev_id)
                        except Exception as update_error:
                            logger.error(
                                f"Failed to update tools for device {dev_id}: {update_error}"
                            )
                            # Don't fail the tool call if update fails

                    return json.dumps(response)

                except TimeoutError:
                    logger.error(f"Timeout executing tool {name} on device {dev_id}")
                    return json.dumps(
                        {
                            "result": None,
                            "error": "Timeout waiting for tool execution",
                            "tool_name": name,
                        }
                    )

                except Exception as e:
                    logger.error(f"Error executing tool {name} on device {dev_id}: {e}")
                    return json.dumps(
                        {"result": None, "error": str(e), "tool_name": name}
                    )

            return handler

        # Create the FunctionTool with proper schema
        tool_obj = FunctionTool(
            name=tool_name,
            description=tool_desc,
            params_json_schema=tool_params,
            on_invoke_tool=make_handler(
                tool_name, device_id, agent_ref, update_callback
            ),
        )

        # Mark as device tool for filtering
        setattr(tool_obj, "_device_tool", True)

        # Check if agent is using an Anthropic model
        is_anthropic = False
        if agent_ref is not None:
            model = getattr(agent_ref, "model", None)
            if model is not None:
                # Model can be a string or a Model object with a 'model' attribute
                model_str = model if isinstance(model, str) else getattr(model, "model", "")
                is_anthropic = "anthropic/" in str(model_str).lower()
        setattr(tool_obj, "_is_anthropic", is_anthropic)

        tool_objects.append(tool_obj)
        logger.debug(f"Created tool wrapper for: {tool_name}")

    logger.info(f"Created {len(tool_objects)} tool wrappers for device {device_id}")
    return tool_objects


async def update_agent_tools(
    agent: Agent,
    device_id: str,
) -> None:
    """
    Re-fetch tools from device and update agent.tools.

    This function is called by tool wrappers after every tool execution
    to ensure the agent always has the latest tool definitions from the device.

    Args:
        agent: The agent whose tools need updating
        device_id: Device to fetch tools from

    Note:
        This function is recursive - it calls parse_device_tools_to_functions
        which creates new tool wrappers that reference this same callback.
        This allows tools to continue updating the agent as needed.
    """
    try:
        logger.info(f"Updating tools for device {device_id}")

        # 1. Fetch latest tools from device
        response = await connection_manager.request_list_tools(device_id, timeout=30.0)
        json_tools = response.get("tools", [])

        if response.get("error"):
            logger.error(
                f"Error fetching tools from device {device_id}: {response.get('error')}"
            )
            return

        # 2. Re-parse into function objects (recursive with same agent and callback)
        device_tools = parse_device_tools_to_functions(
            device_id=device_id,
            json_tools=json_tools,
            agent_ref=agent,
            update_callback=update_agent_tools,  # Same callback for new tools
        )

        # 3. Update agent.tools
        # Keep all pre-existing non-device tools, replace all device tools
        base_tools = [t for t in agent.tools if not getattr(t, "_device_tool", False)]
        agent.tools = base_tools + device_tools

        # Log tool names for debugging
        tool_names = [t.name for t in agent.tools]
        logger.info(
            f"Successfully updated agent tools for device {device_id}: "
            f"{len(device_tools)} device tools, "
            f"{len(base_tools)} base tools, "
            f"{len(agent.tools)} total"
        )
        logger.debug(f"Updated tool list: {', '.join(tool_names)}")

    except TimeoutError:
        logger.error(
            f"Timeout updating tools for device {device_id} - keeping existing tools"
        )

    except Exception as e:
        logger.error(
            f"Failed to update tools for device {device_id}: {e} - keeping existing tools",
            exc_info=True,
        )

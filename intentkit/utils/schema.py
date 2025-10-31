"""JSON Schema utilities for IntentKit.

This module provides utilities for working with JSON schemas, including
resolving $defs references and generating nested schemas.
"""

import copy
from typing import Any


def resolve_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively resolve $defs references in a JSON schema.

    This function takes a JSON schema with $defs references and returns
    a fully nested schema without any $ref pointers. This is useful for
    creating schemas that can be easily consumed by external systems
    that don't support JSON Schema references.

    Args:
        schema: The JSON schema dictionary that may contain $defs and $ref

    Returns:
        dict: A new schema with all $ref resolved to nested objects

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "user": {"$ref": "#/$defs/User"}
        ...     },
        ...     "$defs": {
        ...         "User": {
        ...             "type": "object",
        ...             "properties": {"name": {"type": "string"}}
        ...         }
        ...     }
        ... }
        >>> resolved = resolve_schema_refs(schema)
        >>> # resolved will have the User definition inlined
    """
    # Deep copy to avoid modifying the original
    resolved_schema = copy.deepcopy(schema)

    # Extract $defs if they exist
    defs = resolved_schema.pop("$defs", {})

    def resolve_refs(obj: Any, defs_dict: dict[str, Any]) -> Any:
        """Recursively resolve $ref in an object."""
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"]
                if ref_path.startswith("#/$defs/"):
                    def_name = ref_path.replace("#/$defs/", "")
                    if def_name in defs_dict:
                        # Recursively resolve the referenced definition
                        resolved_def = resolve_refs(defs_dict[def_name], defs_dict)
                        return resolved_def
                    else:
                        # Keep the reference if definition not found
                        return obj
                else:
                    # Keep non-$defs references as is
                    return obj
            else:
                # Recursively process all values in the dictionary
                return {
                    key: resolve_refs(value, defs_dict) for key, value in obj.items()
                }
        elif isinstance(obj, list):
            # Recursively process all items in the list
            return [resolve_refs(item, defs_dict) for item in obj]
        else:
            # Return primitive values as is
            return obj

    # Resolve all references in the schema
    return resolve_refs(resolved_schema, defs)


def create_array_schema(
    item_schema: dict[str, Any], resolve_refs: bool = True
) -> dict[str, Any]:
    """Create an array schema with the given item schema.

    Args:
        item_schema: The schema for array items
        resolve_refs: Whether to resolve $defs references in the item schema

    Returns:
        dict: Array schema with resolved item schema
    """
    if resolve_refs:
        resolved_item_schema = resolve_schema_refs(item_schema)
    else:
        resolved_item_schema = item_schema

    return {
        "type": "array",
        "items": resolved_item_schema,
    }

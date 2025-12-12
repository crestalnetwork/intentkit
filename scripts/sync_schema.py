#!/usr/bin/env python

"""Script to synchronize schema.json files with their corresponding Config classes."""

import json
from collections import OrderedDict
from pathlib import Path

# Root directory of the project
from typing import Any

ROOT_DIR = Path(__file__).parent.parent
SKILLS_DIR = ROOT_DIR / "skills"


def update_enabled_field(schema_path: Path, schema: dict[str, Any]) -> bool:
    """Update the 'enabled' field in the schema.json file.

    Args:
        schema_path: The path to the schema.json file
        schema: The loaded schema dictionary

    Returns:
        bool: True if changes were made, False otherwise
    """
    changes_made = False

    # Check if 'enabled' field is in the schema
    if "enabled" in schema.get("properties", {}):
        # Update the default value to False if it's not already
        if schema["properties"]["enabled"].get("default") is not False:
            schema["properties"]["enabled"]["default"] = False
            changes_made = True
            print(f"Updated 'enabled' default value to False in {schema_path}")
    else:
        # Add the 'enabled' field to the schema properties
        if "properties" not in schema:
            schema["properties"] = {}

        schema["properties"]["enabled"] = {
            "type": "boolean",
            "title": "Enabled",
            "description": "Whether this skill is enabled",
            "default": False,
        }

        # Update the required fields if it exists
        if "required" in schema and "enabled" not in schema["required"]:
            schema["required"].append("enabled")
        elif "required" not in schema:
            schema["required"] = ["enabled"]

        changes_made = True
        print(f"Added 'enabled' field to {schema_path}")

    return changes_made


def update_states_field(schema_path: Path, schema: dict[str, Any]) -> bool:
    """Update the 'states' field in the schema.json file.

    Args:
        schema_path: The path to the schema.json file
        schema: The loaded schema dictionary

    Returns:
        bool: True if changes were made, False otherwise
    """
    changes_made = False

    # Check if 'states' field exists in the schema
    if "states" in schema.get("properties", {}):
        states_schema = schema["properties"]["states"]

        # Ensure states has the correct structure
        if "type" not in states_schema:
            states_schema["type"] = "object"
            changes_made = True

        if "description" not in states_schema:
            skill_name = schema_path.parent.name.capitalize()
            states_schema["description"] = (
                f"States for each {skill_name} skill (disabled, public, or private)"
            )
            changes_made = True

        # Check if properties exists in states
        if "properties" in states_schema:
            # Update each state property to ensure it has the correct enum and default value
            for state_name, state_props in states_schema["properties"].items():
                # Ensure enum values are correct
                if "enum" not in state_props or set(state_props["enum"]) != {
                    "disabled",
                    "public",
                    "private",
                }:
                    state_props["enum"] = ["disabled", "public", "private"]
                    changes_made = True

                # Add or update default value to "disabled"
                if "default" not in state_props or state_props["default"] != "disabled":
                    state_props["default"] = "disabled"
                    changes_made = True

    return changes_made


def reorder_properties(schema: dict[str, Any]) -> bool:
    """Reorder properties to place 'enabled' first.

    Args:
        schema: The loaded schema dictionary

    Returns:
        bool: True if changes were made, False otherwise
    """
    changes_made = False

    if "properties" in schema and "enabled" in schema["properties"]:
        # Create a new ordered dictionary with 'enabled' first
        new_properties = OrderedDict()

        # Add enabled first
        new_properties["enabled"] = schema["properties"]["enabled"]

        # Add all other properties
        for key, value in schema["properties"].items():
            if key != "enabled":
                new_properties[key] = value

        # Replace the properties with the reordered one
        schema["properties"] = new_properties
        changes_made = True

    return changes_made


def update_schema_json(schema_path: Path) -> None:
    """Update the schema.json file with necessary changes.

    Args:
        schema_path: The path to the schema.json file
    """
    # Check if schema.json exists
    if not schema_path.exists():
        print(f"No schema.json found at {schema_path}")
        return

    # Load the existing schema
    with open(schema_path, "r") as f:
        schema = json.load(f)

    # Apply updates
    enabled_changes = update_enabled_field(schema_path, schema)
    states_changes = update_states_field(schema_path, schema)
    order_changes = reorder_properties(schema)

    # Save the schema if changes were made
    if enabled_changes or states_changes or order_changes:
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Updated schema.json at {schema_path}")
    else:
        print(f"No changes needed for {schema_path}")


def main():
    """Main function to synchronize all schema.json files."""
    # Find all schema.json files in the skills directory
    schema_files = list(SKILLS_DIR.glob("*/schema.json"))

    for schema_path in schema_files:
        update_schema_json(schema_path)


if __name__ == "__main__":
    main()

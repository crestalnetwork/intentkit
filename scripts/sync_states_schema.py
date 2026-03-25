#!/usr/bin/env python

"""Script to synchronize states field in schema.json files with Config classes and update descriptions."""

import ast
import json
import os
from pathlib import Path

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent
SKILLS_DIR = ROOT_DIR / "skills"

# Folders to exclude from processing
EXCLUDED_FOLDERS = ["cdp", "goat", "defillama"]


def get_skill_states_from_file(skill_dir: Path) -> set[str] | None:
    """Extract state names from the SkillStates class in __init__.py.

    Args:
        skill_dir: The directory of the skill

    Returns:
        A set of state names if found, None otherwise
    """
    init_file = skill_dir / "__init__.py"
    if not init_file.exists():
        print(f"No __init__.py found in {skill_dir}")
        return None

    try:
        # Read the file content
        with open(init_file, "r") as f:
            content = f.read()

        # Parse the file into an AST
        tree = ast.parse(content)

        # Find the SkillStates class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "SkillStates":
                # Look for annotations in the class
                states = set()
                for child in node.body:
                    if isinstance(child, ast.AnnAssign) and isinstance(
                        child.target, ast.Name
                    ):
                        states.add(child.target.id)
                return states

        print(f"No SkillStates class found in {init_file}")
        return None
    except Exception as e:
        print(f"Error parsing {init_file}: {e}")
        return None


def find_skill_classes(skill_dir: Path) -> dict[str, tuple[str, str]]:
    """Find all skill classes in a skill directory and extract their descriptions.

    Args:
        skill_dir: The directory of the skill

    Returns:
        A dictionary mapping skill class names to (description, file_path) tuples
    """
    skill_classes = {}

    # Walk through all Python files in the skill directory
    for root, _, files in os.walk(skill_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                file_path = Path(root) / file
                try:
                    # Read the file content
                    with open(file_path, "r") as f:
                        content = f.read()

                    # Parse the file into an AST
                    tree = ast.parse(content)

                    # Find classes with a description attribute
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            # Look for a description attribute in the class body
                            for child in node.body:
                                if (
                                    isinstance(child, ast.AnnAssign)
                                    and isinstance(child.target, ast.Name)
                                    and child.target.id == "description"
                                ):
                                    # Check if it's a string assignment
                                    if isinstance(
                                        child.value, ast.Constant
                                    ) and isinstance(child.value.value, str):
                                        description = child.value.value.strip()
                                        class_name = node.name.lower()
                                        skill_classes[class_name] = (
                                            description,
                                            str(file_path),
                                        )
                                elif isinstance(child, ast.Assign):
                                    for target in child.targets:
                                        if (
                                            isinstance(target, ast.Name)
                                            and target.id == "description"
                                        ):
                                            # Check if it's a string assignment
                                            if isinstance(
                                                child.value, ast.Constant
                                            ) and isinstance(child.value.value, str):
                                                description = child.value.value.strip()
                                                class_name = node.name.lower()
                                                skill_classes[class_name] = (
                                                    description,
                                                    str(file_path),
                                                )
                                            # Handle multi-line string literals
                                            elif isinstance(child.value, ast.JoinedStr):
                                                description = ""
                                                for value in child.value.values:
                                                    if isinstance(value, ast.Constant):
                                                        description += str(value.value)
                                                class_name = node.name.lower()
                                                skill_classes[class_name] = (
                                                    description.strip(),
                                                    str(file_path),
                                                )
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")

    return skill_classes


def map_state_to_skill_class(
    state_name: str, skill_classes: dict[str, tuple[str, str]], skill_name: str
) -> str | None:
    """Map a state name to a skill class description.

    Args:
        state_name: The name of the state
        skill_classes: Dictionary of skill classes with their descriptions
        skill_name: The name of the skill directory

    Returns:
        The description of the skill class if found, None otherwise
    """
    # Try direct mapping (state_name -> ClassName)
    # Convert snake_case to CamelCase for class name matching
    class_name = "".join(word.capitalize() for word in state_name.split("_")).lower()
    if class_name in skill_classes:
        return skill_classes[class_name][0]

    # Try with skill name prefix (e.g., "send_message" -> "SlackSendMessage")
    prefixed_class_name = f"{skill_name}{class_name}".lower()
    if prefixed_class_name in skill_classes:
        return skill_classes[prefixed_class_name][0]

    # Try partial matching
    for cls_name, (description, _) in skill_classes.items():
        # Check if the state name is contained in the class name (case insensitive)
        if state_name.lower() in cls_name.lower():
            return description

        # Check if the last part of the state name matches the last part of the class name
        state_parts = state_name.lower().split("_")
        class_parts = cls_name.lower().replace(skill_name.lower(), "").split()

        if state_parts and class_parts and state_parts[-1] == class_parts[-1].lower():
            return description

    return None


def update_states_schema(schema_path: Path) -> None:
    """Update the states field in schema.json files based on SkillStates class and skill descriptions.

    Args:
        schema_path: The path to the schema.json file
    """
    # Check if schema.json exists
    if not schema_path.exists():
        print(f"No schema.json found at {schema_path}")
        return

    # Get the skill directory
    skill_dir = schema_path.parent
    skill_name = skill_dir.name

    # Skip excluded folders
    if skill_name in EXCLUDED_FOLDERS:
        print(f"Skipping {skill_name} as it's in the excluded list")
        return

    # Get the state names from the SkillStates class
    class_states = get_skill_states_from_file(skill_dir)
    if not class_states:
        print(f"No states found for {skill_name}")
        return

    # Find all skill classes and their descriptions
    skill_classes = find_skill_classes(skill_dir)
    if not skill_classes:
        print(f"No skill classes found for {skill_name}")

    # Load the existing schema
    with open(schema_path, "r") as f:
        schema = json.load(f)

    changes_made = False

    # Check if 'states' field exists in the schema
    if "states" not in schema.get("properties", {}):
        # Add the states field
        if "properties" not in schema:
            schema["properties"] = {}

        schema["properties"]["states"] = {
            "type": "object",
            "properties": {},
            "description": f"States for each {skill_name.capitalize()} skill (disabled, public, or private)",
        }
        changes_made = True

    states_schema = schema["properties"]["states"]

    # Ensure states has the correct structure
    if "type" not in states_schema:
        states_schema["type"] = "object"
        changes_made = True

    if "description" not in states_schema:
        states_schema["description"] = (
            f"States for each {skill_name.capitalize()} skill (disabled, public, or private)"
        )
        changes_made = True

    # Ensure properties exists in states
    if "properties" not in states_schema:
        states_schema["properties"] = {}
        changes_made = True

    # Add missing states from the class to the schema
    for state_name in class_states:
        # Get the description from the skill class if available
        description = map_state_to_skill_class(state_name, skill_classes, skill_name)
        default_description = f"State for {state_name}"

        if state_name not in states_schema["properties"]:
            # Add the state to the schema
            states_schema["properties"][state_name] = {
                "type": "string",
                "title": " ".join(word.capitalize() for word in state_name.split("_")),
                "enum": ["disabled", "public", "private"],
                "description": description if description else default_description,
                "default": "disabled",
            }
            changes_made = True
            print(f"Added state '{state_name}' to {schema_path}")
        else:
            # Update existing state
            state_props = states_schema["properties"][state_name]

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

            # Update description if we have a better one from the skill class
            if description and (
                "description" not in state_props
                or state_props["description"] == default_description
            ):
                state_props["description"] = description
                changes_made = True
                print(f"Updated description for state '{state_name}' in {schema_path}")

    # Save the updated schema if changes were made
    if changes_made:
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=2)

        print(f"Updated states schema at {schema_path}")
    else:
        print(f"No changes needed for {schema_path}")


def main():
    """Main function to synchronize all schema.json files."""
    # Find all schema.json files in the skills directory
    schema_files = list(SKILLS_DIR.glob("*/schema.json"))

    for schema_path in schema_files:
        update_states_schema(schema_path)


if __name__ == "__main__":
    main()

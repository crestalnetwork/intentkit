#!/usr/bin/env python3
"""
Generate initial_skills.csv for SkillTable initialization.
"""

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
CDP_INIT = SKILLS_DIR / "cdp" / "__init__.py"
CSV_PATH = PROJECT_ROOT / "skills.csv"

# Categories with platform-provided keys
PLATFORM_KEY_CATEGORIES = [
    "acolyt",
    "allora",
    "elfa",
    "heurist",
    "enso",
    "dapplooker",
    "twitter",
    "cdp",
]

# Default values for fields (excluding created_at, updated_at)
DEFAULTS = {
    "price_tier": 1,
    "price_tier_self_key": 1,
    "rate_limit_count": "",
    "rate_limit_minutes": "",
    "key_provider_agent_owner": False,
    "key_provider_platform": False,
    "key_provider_free": False,
    "author": "",
}


def _get_skill_rows():
    """Collect skill name and category pairs."""
    rows = []
    found_skills = 0
    processed_skills = set()  # Avoid duplicates

    # Process non-cdp categories
    for category_dir in SKILLS_DIR.iterdir():
        if (
            not category_dir.is_dir()
            or category_dir.name.startswith("__")
            or category_dir.name == "cdp"  # cdp is handled separately
        ):
            continue

        category = category_dir.name
        print(f"Processing category: {category}")

        # Process each Python file in the category directory
        for file in category_dir.glob("*.py"):
            if file.name.startswith("__"):
                continue

            # Read the file content to extract skill names directly from the source code
            try:
                content = file.read_text()

                # Look for class definitions that might be skills
                class_pattern = re.compile(r"class\s+([^\(\s]+)[^\n]*:")
                class_matches = class_pattern.finditer(content)

                for match in class_matches:
                    class_name = match.group(1)

                    # Skip base classes
                    if class_name.endswith("BaseTool"):
                        continue

                    # Find the class content - everything after the class definition until the next class or end of file
                    class_start = match.start()
                    next_class = class_pattern.search(content, match.end())
                    if next_class:
                        class_end = next_class.start()
                        class_content = content[class_start:class_end]
                    else:
                        class_content = content[class_start:]

                    # Look for name attribute in the class definition
                    # Pattern: name: str = "skill_name"
                    name_pattern = re.compile(
                        r"\s+name\s*:\s*str\s*=\s*[\'\"]([^\'\"]*)[\'\"](\s|$)"
                    )
                    name_match = name_pattern.search(class_content)
                    if name_match:
                        skill_name = name_match.group(1)

                        # Skip if we've already processed this skill name
                        if skill_name in processed_skills:
                            continue

                        # Add to our results
                        print(
                            f"  Found skill: {class_name} with name='{skill_name}', category={category}"
                        )
                        rows.append((skill_name, category))
                        processed_skills.add(skill_name)
                        found_skills += 1
                    else:
                        print(f"  Skipping {class_name}: couldn't find name attribute")
            except Exception as e:
                print(f"Warning: error processing {file.name}: {e}", file=sys.stderr)
                continue
    # cdp special handling
    lines = CDP_INIT.read_text().splitlines()
    in_states = False
    for line in lines:
        if line.strip().startswith("class SkillStates"):
            in_states = True
            continue
        if in_states:
            stripped = line.strip()
            if not stripped:
                break
            if stripped.startswith("#"):
                continue
            if ":" in stripped:
                state_name = stripped.split(":", 1)[0].strip()
                rows.append((state_name, "cdp"))
    print(
        f"Total skills found: {found_skills} (plus {len(rows) - found_skills} from cdp)"
    )
    return rows


def _check_category_config(category):
    """Check if a category's __init__.py contains a Config with api_key field."""
    init_path = SKILLS_DIR / category / "__init__.py"
    if not init_path.exists():
        return False

    try:
        content = init_path.read_text()
        # Look for Config class with api_key field
        return re.search(r"class\s+Config\b.*?api_key", content, re.DOTALL) is not None
    except Exception:
        return False


def main():
    rows = _get_skill_rows()

    # Process each category to determine key provider settings
    category_settings = {}
    for _, category in rows:
        if category not in category_settings:
            # Check if category needs agent owner key
            key_provider_agent_owner = _check_category_config(category)

            # Check if category has platform-provided keys
            key_provider_platform = category in PLATFORM_KEY_CATEGORIES

            # Set free flag if neither agent owner nor platform provides keys
            key_provider_free = not (key_provider_agent_owner or key_provider_platform)

            category_settings[category] = {
                "key_provider_agent_owner": key_provider_agent_owner,
                "key_provider_platform": key_provider_platform,
                "key_provider_free": key_provider_free,
            }

            print(
                f"Category {category} settings: agent_owner={key_provider_agent_owner}, "
                + f"platform={key_provider_platform}, free={key_provider_free}"
            )

    # Write CSV with appropriate settings for each category
    with CSV_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        header = ["name", "category"] + list(DEFAULTS.keys())
        writer.writerow(header)

        for name, category in sorted(rows, key=lambda x: (x[1], x[0])):
            # Start with default values
            values = dict(DEFAULTS)

            # Override with category-specific settings
            if category in category_settings:
                values.update(category_settings[category])

            # Write the row
            writer.writerow([name, category] + [values[k] for k in DEFAULTS.keys()])

    print(f"Generated {CSV_PATH}")


if __name__ == "__main__":
    main()

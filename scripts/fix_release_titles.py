#!/usr/bin/env python3
"""
Fix GitHub release titles to match version tags.

This script fetches releases from GitHub and updates their titles to match
the version tag if the title is empty or doesn't match the expected format.
"""

import json
import subprocess
import sys
from typing import Any, Dict, List


def run_command(cmd: List[str]) -> str:
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(cmd)}: {e.stderr}")
        sys.exit(1)


def get_releases(limit: int = 20) -> List[Dict[str, Any]]:
    """Get list of releases from GitHub."""
    output = run_command(
        [
            "gh",
            "release",
            "list",
            "--limit",
            str(limit),
            "--json",
            "tagName,name,isDraft,isPrerelease",
        ]
    )
    return json.loads(output)


def update_release_title(tag_name: str, new_title: str, dry_run: bool = False) -> bool:
    """Update release title on GitHub."""
    if dry_run:
        print(f"  [DRY RUN] Would update {tag_name} to title: {new_title}")
        return True

    try:
        run_command(["gh", "release", "edit", tag_name, "--title", new_title])
        print(f"  ✓ Updated {tag_name} to title: {new_title}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to update {tag_name}: {e}")
        return False


def should_fix_title(tag_name: str, current_title: str) -> bool:
    """Determine if a release title needs fixing."""
    # Empty title
    if not current_title or current_title.strip() == "":
        return True

    # Title doesn't match tag
    if current_title != tag_name:
        # Check if it's a commit message format (e.g., "docs: update CHANGELOG.md for v0.8.59")
        if ":" in current_title or "update" in current_title.lower():
            return True

    return False


def main():
    """Main function to fix release titles."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix GitHub release titles to match version tags"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of releases to check (default: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )

    args = parser.parse_args()

    print(f"Fetching last {args.limit} releases...")
    releases = get_releases(args.limit)

    print(f"\nFound {len(releases)} releases\n")

    fixed_count = 0
    skipped_count = 0

    for release in releases:
        tag_name = release["tagName"]
        current_title = release.get("name", "")

        if should_fix_title(tag_name, current_title):
            print(f"Fixing: {tag_name}")
            print(f"  Current title: '{current_title}'")
            print(f"  New title: '{tag_name}'")

            if update_release_title(tag_name, tag_name, args.dry_run):
                fixed_count += 1
        else:
            print(f"Skipping: {tag_name} (title is correct: '{current_title}')")
            skipped_count += 1

    print(f"\n{'=' * 50}")
    print("Summary:")
    print(f"  Fixed: {fixed_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total: {len(releases)}")

    if args.dry_run:
        print("\nThis was a dry run. Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()

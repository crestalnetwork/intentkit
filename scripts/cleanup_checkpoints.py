import argparse
import asyncio
import logging

from intentkit.core.cleanup import cleanup_checkpoints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Cleanup old checkpoints")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Delete threads older than N days (default 90)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Execute deletion (default is dry-run)"
    )
    args = parser.parse_args()

    dry_run = not args.force

    # If dry run, just run it
    if dry_run:
        await cleanup_checkpoints(days=args.days, dry_run=True)
        print("Dry run enabled. No changes made. Use --force to execute.")
        return

    # If force, check count first then ask for confirmation
    # We do a dry run first to get the count
    count = await cleanup_checkpoints(days=args.days, dry_run=True)

    if count == 0:
        return

    confirm = input(
        f"Are you sure you want to delete {count} threads and their history? (y/N): "
    )
    if confirm.lower() != "y":
        print("Aborted.")
        return

    await cleanup_checkpoints(days=args.days, dry_run=False)


if __name__ == "__main__":
    asyncio.run(main())

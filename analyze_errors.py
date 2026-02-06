import re
from collections import defaultdict


def analyze_errors(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()

    error_counts = defaultdict(int)
    file_errors = defaultdict(lambda: defaultdict(int))

    pattern = re.compile(r".* - (error|warning): .* \((report[a-zA-Z]+)\)")

    for line in lines:
        match = pattern.match(line)
        if match:
            level = match.group(1)
            error_type = match.group(2)
            parts = line.split(":")
            if len(parts) > 0:
                filename = parts[0].strip()
                if "/intentkit/" in filename:
                    filename = "intentkit/" + filename.split("/intentkit/")[-1]

                error_counts[f"{level}: {error_type}"] += 1
                file_errors[filename][f"{level}: {error_type}"] += 1

    # Critical error types
    critical_types = [
        "reportCallIssue",
        "reportGeneralTypeIssues",
        "reportAttributeAccessIssue",
        "reportOptionalMemberAccess",
        "reportIndexIssue",
        "reportPossiblyUnboundVariable",
    ]

    print("\n## Critical Errors in Core (excluding tests)")
    print("| File | Error Type | Count |")
    print("|---|---|---|")

    for filename, errors in file_errors.items():
        if "tests/" in filename:
            continue

        for error_key, count in errors.items():
            error_type = error_key.split(": ")[1]
            if error_type in critical_types:
                print(f"| {filename} | {error_type} | {count} |")


if __name__ == "__main__":
    analyze_errors("errors.txt")

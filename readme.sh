#!/bin/bash
# Refresh the "#### Current Date:" line in README.md.
# The line can sit anywhere in the file; if it's missing, it's added at the end.
# Committing and pushing is done by the workflow.
set -euo pipefail

file_path="README.md"
current_date=$(date +"%Y-%m-%d %H:%M:%S")

if grep -q '^#### Current Date: ' "$file_path"; then
    sed -i.bak "s/^#### Current Date: .*/#### Current Date: $current_date/" "$file_path"
    rm -f "$file_path.bak"
else
    printf '\n#### Current Date: %s\n' "$current_date" >> "$file_path"
fi

echo "Current date $current_date has been written to $file_path."

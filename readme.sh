#!/bin/bash

# Define the file path
file_path="README.md"

# Get the current date and time
current_date=$(date +"%Y-%m-%d %H:%M:%S")

# Check if the file already contains a date and time at the beginning
if [[ $(head -n 1 "$file_path") == "#### Current Date: "* ]]; then
    # If it exists, replace the existing date and time with the current one
    sed -i "1s/.*/#### Current Date: $current_date/" "$file_path"
else
    # If it doesn't exist, add the current date and time at the beginning
    echo -e "#### Current Date: $current_date\n\n$(cat $file_path)" > "$file_path"
fi

echo "Current date $current_date has been added to the file."

git add README.md
git commit -m "Update date in readme"
git push origin main

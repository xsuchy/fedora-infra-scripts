#!/usr/bin/python3
"""
Can you write a Python script that read CSV file? Ignore first 3 lines. Fourth line is a header of a columns. If the column with name "appcode" is equal to "copr-001" or column "Resource Group Name" is equal to "copr" then calculate sum of values from column "Cost" of such rows that match the condition.
The name of the file will be passed as command line argument.
"""

import csv
import sys

def not_none(value, default):
    if value is None:
        return default
    else:
        return value

def calculate_cost_sum(file_path):
    try:
        with open(file_path, 'r') as csvfile:
            # Skip the first three lines
            for _ in range(3):
                next(csvfile)

            # Read the header row
            reader = csv.DictReader(csvfile)
            
            # Validate the required columns
            required_columns = ["appcode", "Resource Group Name", "Cost"]
            if not all(col in reader.fieldnames for col in required_columns):
                raise ValueError(f"CSV file must contain the following columns: {', '.join(required_columns)}")

            # Calculate the sum of the "Cost" column based on the conditions
            total_cost = 0.0
            for row in reader:
                try:
                    appcode = not_none(row["appcode"], "").strip()
                    resource_group_name = not_none(row["Resource Group Name"], "").strip()
                    cost = float(not_none(row["Cost"], "0").strip())

                    if appcode == "copr-001" or resource_group_name == "copr":
                        total_cost += cost
                except ValueError:
                    # Handle cases where the "Cost" column cannot be converted to float
                    print(f"Skipping row with invalid cost value: {row}")

            return total_cost

    except FileNotFoundError:
        print(f"File not found: {file_path}")

if len(sys.argv) < 2:
    print("Usage: python script.py <file_path>")
    sys.exit(1)

file_path = sys.argv[1]
total_cost = calculate_cost_sum(file_path)
if total_cost is not None:
    print(f"Total Cost: {total_cost}")

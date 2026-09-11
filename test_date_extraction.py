import re

def extract_date_from_folder(folder_name):
    """Extract date from folder name if it starts with YYMMDD."""
    # Match YYMMDD at start of string
    match = re.match(r'^(\d{2})(\d{2})(\d{2})', folder_name)
    if match:
        year, month, day = match.groups()
        # Assume 20xx for year
        return f"20{year}-{month}-{day}"
    return None

test_cases = [
    "251031-databricks-ciencia-datos",
    "251104-mini-cisco",
    "230101-old-project",
    "no-date-project",
    "2512-invalid-date",
    "PPT_Templates"
]

print("Testing date extraction:")
for folder in test_cases:
    date = extract_date_from_folder(folder)
    print(f"  {folder} -> {date}")

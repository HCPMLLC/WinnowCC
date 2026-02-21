"""Test the role filtering logic."""

from app.services.matching import ROLE_FAMILIES, _is_title_compatible

# Test data
target_titles = ["Project Manager", "Program Manager", "PMO Director"]
test_jobs = [
    "Senior Data Scientist",
    "Data Scientist",
    "Senior Project Manager",
    "Program Manager",
    "DevOps Engineer",
    "Site Reliability Engineer",
    "Project Coordinator",
    "Scrum Master",
    "Software Engineer",
    "Executive Assistant",
]

print("=== TESTING ROLE FILTERING ===")
print(f"Candidate target titles: {target_titles}\n")

for job_title in test_jobs:
    result = _is_title_compatible(job_title.lower(), target_titles)
    status = "PASS" if result else "BLOCKED"
    print(f"{status}: {job_title}")

# Check what family PM falls into
print("\n=== CHECKING ROLE FAMILIES ===")
for family_name, family_data in ROLE_FAMILIES.items():
    for target in target_titles:
        target_lower = target.lower()
        if any(kw in target_lower for kw in family_data["keywords"]):
            print(f"'{target}' matches family: {family_name}")
            print(f"  Keywords: {family_data['keywords'][:5]}...")
            print(f"  Excludes: {family_data['exclude'][:5]}...")
            break

# Manual check for data scientist
print("\n=== MANUAL CHECK ===")
job_title = "senior data scientist"
exclude_list = ROLE_FAMILIES["project_management"]["exclude"]
print(f"Job title: '{job_title}'")
print(f"Exclude terms: {exclude_list}")
for excl in exclude_list:
    if excl in job_title:
        print(f"  FOUND: '{excl}' in '{job_title}'")

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path

from app.services.profile_parser import extract_text, parse_profile_from_text

path = Path(
    r"C:\Users\ronle\Documents\resumematch\services\api\data\uploads\b2b2b7ca627548018f0814a39e485fb8_Frances W Levi Resume 2019.docx"
)
raw = extract_text(path)
profile = parse_profile_from_text(raw)

print("=== Basics ===")
print(json.dumps(profile["basics"], indent=2))
print()
print("=== Skills ===")
print(profile["skills"])
print()
print("=== Experience dates ===")
for i, exp in enumerate(profile["experience"]):
    print(
        f"  {i}: {exp.get('company')} | start={exp.get('start_date')} | end={exp.get('end_date')}"
    )

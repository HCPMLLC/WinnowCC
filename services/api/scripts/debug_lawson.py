import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path

from app.services.profile_parser import extract_text, parse_profile_from_text

path = Path(
    r"C:\Users\ronle\Documents\resumematch\services\api\data\uploads\23c26d485e0d461aba899558dfb34e1a_Michael Lawson Resume March 2025.docx"
)
raw = extract_text(path)

print("=== First 20 lines ===")
for i, line in enumerate(raw.splitlines()[:20]):
    print(f"  {i}: [{line}]")

print()
profile = parse_profile_from_text(raw)
print("=== Basics ===")
print(json.dumps(profile["basics"], indent=2))

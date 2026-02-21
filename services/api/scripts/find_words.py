import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path

from app.services.profile_parser import extract_text

raw = extract_text(
    Path(
        r"data\uploads\b2b2b7ca627548018f0814a39e485fb8_Frances W Levi Resume 2019.docx"
    )
)
for i, line in enumerate(raw.splitlines()):
    low = line.lower()
    if "assembly" in low or "aurora" in low:
        print(f"  {i}: {line}")

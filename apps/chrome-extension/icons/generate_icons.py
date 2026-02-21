"""Generate Chrome extension PNG icons by resizing the Gold GBG 1024x1024 source.

Produces icon16.png, icon48.png, icon128.png from the high-res source image.
Requires Pillow (pip install Pillow).
"""

import os
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(SCRIPT_DIR, "Gold GBG 1024x1024.png")
SIZES = [16, 48, 128]


if __name__ == "__main__":
    src = Image.open(SOURCE)
    # Convert to RGBA if not already
    if src.mode != "RGBA":
        src = src.convert("RGBA")

    for size in SIZES:
        icon = src.resize((size, size), Image.LANCZOS)
        path = os.path.join(SCRIPT_DIR, f"icon{size}.png")
        icon.save(path, "PNG")
        print(f"Created: {path} ({size}x{size})")

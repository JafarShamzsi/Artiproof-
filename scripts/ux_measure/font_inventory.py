"""Read-only cmap/hash inventory. Requires fontTools in an existing scratch venv."""
import hashlib
import json
from pathlib import Path

from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[2] / "frontend/src/app/fonts"
glyphs = "ƏəĞğİıÖöŞşÇçÜü"
inventory = []
for path in sorted(root.glob("*.ttf")):
    with TTFont(path) as font:
        cmap = font.getBestCmap()
        missing = [char for char in glyphs if ord(char) not in cmap]
        inventory.append({"file": path.name, "bytes": path.stat().st_size,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "tested_glyphs": glyphs, "missing": missing})
print(json.dumps(inventory, ensure_ascii=True, indent=2))
assert len(inventory) == 5 and all(not item["missing"] for item in inventory)

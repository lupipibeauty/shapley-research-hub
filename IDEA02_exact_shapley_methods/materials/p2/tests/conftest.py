import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for folder in (ROOT/"generators",ROOT/"oracles",ROOT/"algorithms",ROOT/"utilities"):
    sys.path.insert(0,str(folder))


import sys
from pathlib import Path

# Lambda imports use sibling modules (schemas, service); need orders dir on path.
_root = Path(__file__).resolve().parents[2]
orders_path = str(_root / "src" / "orders")
src_path = str(_root / "src")
for path in [orders_path, src_path]:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

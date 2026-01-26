import sys
from pathlib import Path

# Para testes de products, força src/products no topo absoluto do path
_root = Path(__file__).resolve().parents[2]
products_path = str(_root / "src" / "products")
src_path = str(_root / "src")

# Remove se já existir e reinsere no topo
for path in [products_path, src_path]:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

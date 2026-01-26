import sys
from pathlib import Path

# Para testes de payment, força src/payment no topo absoluto do path
_root = Path(__file__).resolve().parents[2]
payment_path = str(_root / "src" / "payment")
src_path = str(_root / "src")

# Remove se já existir e reinsere no topo
for path in [payment_path, src_path]:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

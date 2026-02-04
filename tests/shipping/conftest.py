import importlib.util
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
shipping_path = str(_root / "src" / "shipping")
payment_path = str(_root / "src" / "payment")
src_path = str(_root / "src")

for p in (payment_path, src_path, shipping_path):
    while p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, shipping_path)
sys.path.insert(0, src_path)

# Para "from schemas import" / "from service import" resolverem para shipping ao
# carregar src.shipping.handler e service (evita conflito com payment quando path tem payment primeiro).
def _inject_shipping_modules():
    spec_s = importlib.util.spec_from_file_location("schemas", _root / "src" / "shipping" / "schemas.py")
    spec_sv = importlib.util.spec_from_file_location("service", _root / "src" / "shipping" / "service.py")
    if spec_s and spec_s.loader and spec_sv and spec_sv.loader:
        mod_s = importlib.util.module_from_spec(spec_s)
        mod_sv = importlib.util.module_from_spec(spec_sv)
        sys.modules["schemas"] = mod_s
        sys.modules["service"] = mod_sv
        spec_s.loader.exec_module(mod_s)
        spec_sv.loader.exec_module(mod_sv)

_inject_shipping_modules()

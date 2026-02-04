import importlib.util
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
payment_path = str(_root / "src" / "payment")
src_path = str(_root / "src")

for path in [payment_path, src_path]:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

# Garante que "from schemas import" e "from service import" no handler de payment resolvam para payment
for _name, _file in (("schemas", "schemas.py"), ("service", "service.py")):
    _spec = importlib.util.spec_from_file_location(_name, _root / "src" / "payment" / _file)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules[_name] = _mod
        _spec.loader.exec_module(_mod)

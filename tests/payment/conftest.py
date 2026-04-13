import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_root = Path(__file__).resolve().parents[2]
payment_path = str(_root / "src" / "payment")
src_path = str(_root / "src")

for path in [payment_path, src_path]:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

# Evita importar firebase_admin (não instalado em dev); service importa shared.firebase
_safe_firebase = MagicMock()
_safe_firebase.decrement_products_quantity = lambda items: None
sys.modules["shared.firebase"] = _safe_firebase

# Garante que imports no estilo Lambda (schemas, service, exceptions) apontem para src/payment/*
# e que src.payment.exceptions seja o mesmo objeto de módulo (evita except que não casa nos testes).
for _name, _file in (
    ("schemas", "schemas.py"),
    ("service", "service.py"),
    ("exceptions", "exceptions.py"),
):
    _spec = importlib.util.spec_from_file_location(_name, _root / "src" / "payment" / _file)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules[_name] = _mod
        _spec.loader.exec_module(_mod)
        if _name == "exceptions":
            sys.modules["src.payment.exceptions"] = _mod

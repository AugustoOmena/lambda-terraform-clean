"""Path e módulo único para o pacote webhook (evita colisão com tests/payment/conftest ``service``)."""

import importlib.util
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
_webhook_dir = _root / "src" / "webhook"
_src = str(_root / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
_wh_path = str(_webhook_dir)
if _wh_path not in sys.path:
    sys.path.insert(0, _wh_path)

_spec = importlib.util.spec_from_file_location("webhook_me_service", _webhook_dir / "service.py")
assert _spec and _spec.loader
_webhook_mod = importlib.util.module_from_spec(_spec)
sys.modules["webhook_me_service"] = _webhook_mod
try:
    _spec.loader.exec_module(_webhook_mod)
finally:
    if _wh_path in sys.path:
        sys.path.remove(_wh_path)

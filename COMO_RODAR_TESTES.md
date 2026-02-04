# 🧪 Guia: Como Rodar os Testes Localmente (MacOS)

## ✅ Problema Resolvido

Este projeto estava com **2 problemas críticos** que impediam a execução local do pytest:

### 1. **Conflito de Binários (Linux vs Mac)**
- **Causa**: As bibliotecas compiladas em `src/layers/` são para AWS Lambda (Linux)
- **Sintoma**: `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`
- **Solução**: Configuramos `pytest.ini` para **IGNORAR** a pasta `src/layers/`

### 2. **Import Shadowing (Ambiguidade de Imports)**
- **Causa**: Múltiplos arquivos `service.py`, `repository.py`, etc.
- **Sintoma**: `ImportError: cannot import name ...` (Python carregava o arquivo errado)
- **Solução**: Convertemos **TODOS** os imports para **Imports Absolutos**

---

## 📋 Pré-requisitos

1. **Python 3.11+** instalado
2. **Dependências locais** instaladas (NÃO use as de `src/layers/`):

### **Instalação Automática (RECOMENDADO)**

```bash
# 1. Ative o ambiente virtual (se já existe)
source .venv/bin/activate

# 2. Execute o script de instalação
./install_test_dependencies.sh

# OU instale manualmente:
pip install pytest pytest-cov pydantic "aws-lambda-powertools[all]" supabase mercadopago
```

### **Instalação Manual**

```bash
# Opção A: Com ambiente virtual (recomendado)
python3 -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install pytest pytest-cov pydantic "aws-lambda-powertools[all]" supabase mercadopago

# Opção B: Instalação global (mais simples, mas menos isolado)
python3 -m pip install pytest pytest-cov pydantic "aws-lambda-powertools[all]" supabase mercadopago
```

---

## 🚀 Como Rodar os Testes

### **Importante: Por que `pytest` não funciona?**

Se você executar apenas `pytest` e receber `command not found`, é porque:
1. ❌ O pytest não está instalado
2. ❌ Você não ativou o ambiente virtual

**Soluções:**

```bash
# Solução 1: Ative o ambiente virtual primeiro (RECOMENDADO)
source .venv/bin/activate
pytest tests/payment/ -v

# Solução 2: Use python3 -m pytest (funciona sem ativar venv)
python3 -m pytest tests/payment/ -v

# Solução 3: Instale pytest globalmente
python3 -m pip install pytest
pytest tests/payment/ -v
```

### **Rodar TODOS os testes**
```bash
# Com venv ativado:
pytest

# Sem venv:
python3 -m pytest
```

### **Rodar todos (shipping + shared + payment) em duas invocações**
Por causa do conflito de módulos `schemas`/`service` entre shipping e payment, rode primeiro shipping e depois o restante:
```bash
python3 -m pytest tests/shipping/ -q && python3 -m pytest tests/shared/ tests/payment/ tests/orders/ tests/products/ tests/profiles/ -q
```

### **Rodar testes de um módulo específico**
```bash
pytest tests/payment/ -v
pytest tests/products/ -v
pytest tests/profiles/ -v
```

### **Rodar um arquivo específico**
```bash
pytest tests/payment/test_handler.py -v
pytest tests/payment/test_service_audit.py -v
```

### **Rodar um teste específico**
```bash
pytest tests/payment/test_handler.py::TestPaymentLambdaHandler::test_handler_success_201_creates_payment -v
```

### **Opções úteis**
```bash
# Verbose (mostra cada teste)
pytest -v

# Mostra print() statements
pytest -s

# Para no primeiro erro
pytest -x

# Mostra coverage
pytest --cov=src --cov-report=html
```

---

## 📁 Estrutura de Imports (Absolutos)

### ✅ **CORRETO** (Imports Absolutos)
```python
# Em src/payment/service.py
from src.payment.repository import PaymentRepository
from src.payment.schemas import PaymentInput

# Em tests/payment/test_service.py
from src.payment.service import PaymentService
from src.payment.schemas import PaymentInput
```

### ❌ **ERRADO** (Imports Relativos/Implícitos)
```python
# NUNCA faça isso!
from repository import PaymentRepository  # Ambíguo!
from schemas import PaymentInput           # Pode pegar o arquivo errado!
```

---

## 🛠️ Configuração Aplicada

### **pytest.ini** (Raiz do projeto)
```ini
[pytest]
# Define a raiz como ponto de partida
pythonpath = .

# CRÍTICO: Ignora layers (binários Linux)
norecursedirs = src/layers infra .venv .git __pycache__ .pytest_cache node_modules

# Configurações de output
addopts = -v --tb=short --strict-markers

# Descoberta de testes
testpaths = tests
```

---

## 🔍 Arquivos Corrigidos

### **src/** (13 imports corrigidos)
- `src/payment/handler.py` ✅
- `src/payment/service.py` ✅
- `src/products/handler.py` ✅
- `src/products/service.py` ✅
- `src/profiles/handler.py` ✅
- `src/profiles/service.py` ✅
- `src/profiles/repository.py` ✅

### **tests/** (40+ imports corrigidos)
- `tests/payment/test_handler.py` ✅
- `tests/payment/test_repository.py` ✅
- `tests/payment/test_schemas.py` ✅
- `tests/payment/test_service_audit.py` ✅
- `tests/payment/test_service_integration.py` ✅
- `tests/products/test_handler.py` ✅
- `tests/products/test_service.py` ✅
- `tests/profiles/test_repository.py` ✅
- `tests/profiles/test_service.py` ✅

---

## 🎯 Resultado Esperado

Ao rodar `pytest tests/payment/ -v`, você deve ver:

```
========================= test session starts ==========================
platform darwin -- Python 3.11.9, pytest-8.0.0
rootdir: /path/to/lambda-terraform-clean
configfile: pytest.ini
testpaths: tests
collected 45 items

tests/payment/test_handler.py::TestPaymentLambdaHandler::test_handler_success_201_creates_payment PASSED [ 2%]
tests/payment/test_handler.py::TestPaymentLambdaHandler::test_handler_validation_error_400... PASSED [ 4%]
...
========================= 45 passed in 2.34s ===========================
```

---

## 🐛 Troubleshooting

### **Erro: `pytest: command not found`**
```bash
# Causa: pytest não está instalado ou venv não está ativado

# Solução 1: Ative o ambiente virtual
source .venv/bin/activate
pip install pytest

# Solução 2: Use python3 -m pytest
python3 -m pip install pytest
python3 -m pytest tests/payment/ -v

# Verificar se pytest está instalado:
python3 -m pip show pytest
```

### **Erro: ModuleNotFoundError: No module named 'pydantic'**
```bash
# Solução: Instale as dependências localmente
python3 -m pip install pydantic aws-lambda-powertools supabase mercadopago
```

### **Erro: ImportError: cannot import name 'PaymentService'**
```bash
# Solução: Verifique que você está usando imports ABSOLUTOS
# Corrija: from service import PaymentService
# Para:    from src.payment.service import PaymentService
```

### **Erro: pydantic_core._pydantic_core not found**
```bash
# Solução: Verifique que pytest.ini tem 'norecursedirs = src/layers'
# Se persistir, delete __pycache__:
find . -type d -name __pycache__ -exec rm -rf {} +
```

---

## 📚 Referências

- **Pytest Docs**: https://docs.pytest.org/
- **Pydantic V2**: https://docs.pydantic.dev/latest/
- **Python Import System**: https://docs.python.org/3/reference/import.html

---

## ✅ Checklist Final

- [x] `pytest.ini` configurado na raiz
- [x] Todos os imports em `src/` são absolutos
- [x] Todos os imports em `tests/` são absolutos
- [x] `src/__init__.py` existe
- [x] Dependências instaladas localmente
- [x] Sintaxe validada em todos os arquivos

**Pronto para rodar:** `pytest tests/ -v` 🚀

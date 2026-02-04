import os
from typing import Any, List

import firebase_admin
from firebase_admin import credentials, db
from aws_lambda_powertools import Logger

logger = Logger(service="firebase")

_firebase_db = None


def get_firebase_db():
    """
    Initializes Firebase Admin SDK with service account credentials from environment variables.
    
    Returns singleton reference to Firebase Realtime Database.
    
    Raises:
        ValueError: If required environment variables are missing.
    """
    global _firebase_db
    
    if _firebase_db is not None:
        return _firebase_db
    
    try:
        firebase_admin.get_app()
        logger.info("Firebase Admin SDK already initialized (reusing existing app)")
    except ValueError:
        project_id = os.environ.get("FIREBASE_PROJECT_ID")
        client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
        private_key = os.environ.get("FIREBASE_PRIVATE_KEY")
        database_url = os.environ.get("FIREBASE_DATABASE_URL")
        
        if not all([project_id, client_email, private_key, database_url]):
            raise ValueError("Firebase credentials missing (ENV VARS)")
        
        private_key = private_key.replace('\\n', '\n')
        
        cred_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        try:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {
                'databaseURL': database_url
            })
            logger.info("Firebase Admin SDK initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            raise
    
    _firebase_db = db.reference()
    return _firebase_db


def get_product_by_id(product_id: int):
    """
    Lê apenas o nó do produto no Firebase (products/{id}). Não carrega a árvore inteira.

    Returns:
        Dict do produto ou None se não existir.
    """
    try:
        ref = get_firebase_db().child("products").child(str(product_id))
        return ref.get()
    except Exception as e:
        logger.error(f"Firebase get product {product_id} failed: {e}")
        return None


def decrement_products_quantity(items: List[Any]) -> None:
    """
    Atualiza no Firebase a quantidade dos produtos vendidos (subtrai do estoque),
    como uma edição de backoffice: apenas os itens vendidos, pelo ID.

    Para cada item: lê só esse produto por ID (get_product_by_id), subtrai
    a quantidade vendida do tamanho correspondente (ou 'Único'), recalcula o total
    e faz update apenas nesse nó. Custo: 1 read + 1 write por item do pedido.

    Args:
        items: Lista de itens com .id, .quantity e opcionalmente .size (default 'Único').
    """
    if not items:
        return
    try:
        get_firebase_db()
    except Exception as e:
        logger.error(f"Firebase unavailable for stock update: {e}")
        return

    for item in items:
        product_id = getattr(item, "id", None)
        sold_qty = getattr(item, "quantity", 0)
        size_sold = getattr(item, "size", None) or "Único"
        if product_id is None or sold_qty <= 0:
            continue
        try:
            data = get_product_by_id(product_id)
            if not data:
                logger.warning(f"Product {product_id} not found in Firebase, skipping quantity update")
                continue
            current_stock = data.get("stock")
            if not isinstance(current_stock, dict):
                current_stock = {}
            if size_sold in current_stock:
                current_stock[size_sold] = max(0, int(current_stock[size_sold]) - sold_qty)
            else:
                if "Único" in current_stock:
                    current_stock["Único"] = max(0, int(current_stock["Único"]) - sold_qty)
            new_total = sum(int(v) for v in current_stock.values())
            ref = get_firebase_db().child("products").child(str(product_id))
            ref.update({"quantity": new_total, "stock": current_stock})
            logger.info(f"Firebase: product {product_id} quantity updated (sold {sold_qty}, new total {new_total})")
        except Exception as e:
            logger.error(f"Firebase stock update failed for product {product_id}: {e}")

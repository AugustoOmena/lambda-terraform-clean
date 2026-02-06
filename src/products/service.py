import io
import csv
from aws_lambda_powertools import Logger
from repository import ProductRepository
from schemas import ProductInput, ProductUpdate
from shared.firebase import set_product_consolidated

logger = Logger(service="products")

class ProductService:
    def __init__(self):
        self.repo = ProductRepository()

    # Recebe filters agora
    def list_products(self, page: int, limit: int, filters: dict = None):
        start = (page - 1) * limit
        end = start + limit - 1
        
        # Passa filters para o repo
        data, total = self.repo.get_products_paginated(start, end, filters)
        
        for p in data:
            if p.get("image") and not p.get("images"):
                p["images"] = [p["image"]]

        has_next = (page * limit) < total
        next_page = (page + 1) if has_next else None

        return {
            "data": data,
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "nextPage": next_page
            }
        }

    def get_product(self, product_id: int):
        product = self.repo.get_by_id(product_id)
        if not product:
            return None
        variants = self.repo.get_variants_by_product_id(product_id)
        product["variants"] = variants
        return product

    def create_product(self, payload: ProductInput):
        data = payload.model_dump(mode="json", exclude_none=True)
        variants = data.pop("variants", [])
        if variants:
            data["quantity"] = sum(v["stock_quantity"] for v in variants)
            data["stock"] = {}
        product = self.repo.create(data)
        if not product:
            return None
        product_id = product["id"]
        self.repo.insert_variants(product_id, variants)
        self._sync_consolidated_to_firebase(product_id, product, variants)
        return self.get_product(product_id)

    def update_product(self, product_id: int, payload: ProductUpdate):
        current_product = self.repo.get_by_id(product_id)
        if current_product:
            old_image = current_product.get("image")
            new_image = payload.image
            if old_image and old_image != new_image:
                self.repo.delete_storage_file(old_image)

        data = payload.model_dump(mode="json", exclude_none=True)
        variants = data.pop("variants", None)
        if variants is not None:
            self.repo.delete_variants_by_product_id(product_id)
            self.repo.insert_variants(product_id, variants)
            data["quantity"] = sum(v["stock_quantity"] for v in variants)
            data["stock"] = {}
        updated_product = self.repo.update(product_id, data)
        if not updated_product:
            return None
        variants = self.repo.get_variants_by_product_id(product_id)
        self._sync_consolidated_to_firebase(product_id, updated_product, variants)
        return self.get_product(product_id)

    def delete_product(self, product_id: int):
        current_product = self.repo.get_by_id(product_id)
        if current_product and current_product.get("image"):
            self.repo.delete_storage_file(current_product.get("image"))
        
        result = self.repo.delete(product_id)
        
        if result:
            self._sync_firebase_delete(product_id)
        return result

    def export_products_csv(self):
        products = self.repo.get_all_raw()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Nome", "Preco", "Categoria", "Estoque", "Tamanho", "Criado em"])
        for p in products:
            writer.writerow([
                p.get("id"),
                p.get("name"),
                f"{p.get('price', 0):.2f}",
                p.get("category"),
                p.get("quantity"),
                p.get("size"),
                p.get("created_at")
            ])
        return output.getvalue()
    
    def _sync_consolidated_to_firebase(self, product_id: int, product: dict, variants: list):
        """Sincroniza produto + variantes no Firebase no formato consolidado."""
        try:
            price_raw = product.get("price")
            price = float(price_raw) if price_raw is not None else 0.0
            images = product.get("images") or []
            if not images and product.get("image"):
                images = [product["image"]]
            payload = {
                "id": str(product_id),
                "name": product.get("name") or "",
                "description": product.get("description") or "",
                "category": product.get("category") or "",
                "material": product.get("material") or "",
                "print": product.get("pattern") or "",
                "price": price,
                "image": product.get("image") or "",
                "images": images,
                "variants": [
                    {"color": v.get("color", ""), "size": v.get("size", ""), "stock": int(v.get("stock_quantity", 0))}
                    for v in variants
                ],
            }
            set_product_consolidated(payload)
        except Exception as e:
            logger.error(f"Firebase consolidated sync failed for product {product_id}: {str(e)}")

    def _sync_firebase_delete(self, product_id: int):
        try:
            from shared.firebase import get_firebase_db
            get_firebase_db().child("products").child(str(product_id)).delete()
            logger.info(f"Product {product_id} deleted from Firebase")
        except Exception as e:
            logger.error(f"Firebase delete failed for product {product_id}: {str(e)}")
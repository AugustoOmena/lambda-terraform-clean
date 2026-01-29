import io
import csv
from aws_lambda_powertools import Logger
from repository import ProductRepository
from schemas import ProductInput, ProductUpdate, serialize_for_firebase
from shared.firebase import get_firebase_db

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
        return self.repo.get_by_id(product_id)

    def create_product(self, payload: ProductInput):
        product = self.repo.create(payload.model_dump(mode='json', exclude_none=True))
        
        if product:
            self._sync_to_firebase(product, operation="create")
        
        return product

    def update_product(self, product_id: int, payload: ProductUpdate):
        current_product = self.repo.get_by_id(product_id)
        if current_product:
            old_image = current_product.get("image")
            new_image = payload.image
            if old_image and old_image != new_image:
                self.repo.delete_storage_file(old_image)

        updated_product = self.repo.update(product_id, payload.model_dump(mode='json', exclude_none=True))
        
        if updated_product:
            self._sync_to_firebase(updated_product, operation="update")
        
        return updated_product

    def delete_product(self, product_id: int):
        current_product = self.repo.get_by_id(product_id)
        if current_product and current_product.get("image"):
            self.repo.delete_storage_file(current_product.get("image"))
        
        result = self.repo.delete(product_id)
        
        if result:
            self._sync_to_firebase_delete(product_id)
        
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
    
    def _sync_to_firebase(self, product: dict, operation: str):
        """
        Syncs product data to Firebase Realtime Database.
        
        Firebase acts as a read model for the frontend. If sync fails,
        it's logged but doesn't break the Supabase transaction.
        
        Args:
            product: Product dict from Supabase
            operation: 'create' or 'update'
        """
        try:
            firebase_db = get_firebase_db()
            product_id = product.get("id")
            
            if not product_id:
                logger.warning("Product missing ID, skipping Firebase sync")
                return
            
            firebase_data = serialize_for_firebase(product)
            ref = firebase_db.child("products").child(str(product_id))
            ref.set(firebase_data)
            
            logger.info(f"Product {product_id} synced to Firebase ({operation})")
            
        except Exception as e:
            logger.error(f"Firebase sync failed for product {product.get('id')}: {str(e)}")
    
    def _sync_to_firebase_delete(self, product_id: int):
        """
        Removes product from Firebase Realtime Database.
        
        Args:
            product_id: Product ID to delete
        """
        try:
            firebase_db = get_firebase_db()
            ref = firebase_db.child("products").child(str(product_id))
            ref.delete()
            
            logger.info(f"Product {product_id} deleted from Firebase")
            
        except Exception as e:
            logger.error(f"Firebase delete failed for product {product_id}: {str(e)}")
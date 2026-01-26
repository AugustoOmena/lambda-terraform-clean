import io
import csv
from repository import ProductRepository
from schemas import ProductInput, ProductUpdate

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
        return self.repo.create(payload.model_dump(exclude_none=True))

    def update_product(self, product_id: int, payload: ProductUpdate):
        current_product = self.repo.get_by_id(product_id)
        if current_product:
            old_image = current_product.get("image")
            new_image = payload.image
            if old_image and old_image != new_image:
                self.repo.delete_storage_file(old_image)

        return self.repo.update(product_id, payload.model_dump(exclude_none=True))

    def delete_product(self, product_id: int):
        current_product = self.repo.get_by_id(product_id)
        if current_product and current_product.get("image"):
            self.repo.delete_storage_file(current_product.get("image"))
        return self.repo.delete(product_id)

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
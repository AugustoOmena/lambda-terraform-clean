from shared.database import get_supabase_client

class ProductRepository:
    def __init__(self):
        self.db = get_supabase_client()
        self.bucket = "product-images"

    def get_products_paginated(self, start: int, end: int, filters: dict = None):
        # count="exact" garante que o retorno inclua o total de itens FILTRADOS
        query = self.db.table("products").select("*", count="exact")

        if filters:
            # 1. Filtro de Nome (Case Insensitive)
            if filters.get("name"):
                query = query.ilike("name", f"%{filters['name']}%")
            
            # 2. Filtro de Categoria
            if filters.get("category"):
                query = query.eq("category", filters["category"])

            # 3. Filtros de Preço
            if filters.get("min_price"):
                query = query.gte("price", filters["min_price"])
            if filters.get("max_price"):
                query = query.lte("price", filters["max_price"])
            
            # 4. Filtro de TAMANHO (O Pulo do Gato para JSON)
            # Verifica se stock->>TAMANHO é maior que 0
            if filters.get("size"):
                size = filters["size"]
                # Sintaxe do PostgREST para acessar JSON: coluna->>chave
                # Queremos: stock->>size > 0
                query = query.gt(f"stock->>{size}", 0)

            # 5. Ordenação
            sort_type = filters.get("sort", "newest")
            if sort_type == "qty_asc":
                query = query.order("quantity", desc=False)
            elif sort_type == "qty_desc":
                query = query.order("quantity", desc=True)
            elif sort_type == "oldest":
                query = query.order("id", desc=False)
            else: # newest
                query = query.order("id", desc=True)
        else:
            query = query.order("id", desc=True)

        # Range (Paginação)
        res = query.range(start, end).execute()
        
        # res.count aqui será o total de itens QUE BATEM COM OS FILTROS
        # res.data são os itens da página atual
        return res.data, res.count

    def get_all_raw(self):
        res = self.db.table("products").select("*").order("id", desc=True).execute()
        return res.data

    def get_by_id(self, product_id: int):
        res = self.db.table("products").select("*").eq("id", product_id).execute()
        return res.data[0] if res.data else None

    def get_variants_by_product_id(self, product_id: int):
        res = self.db.table("product_variants").select("*").eq("product_id", product_id).execute()
        return res.data or []

    def create(self, data: dict):
        data = {k: v for k, v in data.items() if k != "variants"}
        if "stock" not in data or not data["stock"]:
            data["stock"] = {"Único": data.get("quantity", 0)}
        res = self.db.table("products").insert(data).execute()
        return res.data[0] if res.data else None

    def insert_variants(self, product_id: int, variants: list) -> None:
        if not variants:
            return
        rows = []
        for v in variants:
            sku = v.get("sku") or f"{product_id}-{v['color']}-{v['size']}"
            rows.append({
                "product_id": product_id,
                "color": v["color"],
                "size": v["size"],
                "stock_quantity": v.get("stock_quantity", 0),
                "sku": sku,
            })
        self.db.table("product_variants").insert(rows).execute()

    def delete_variants_by_product_id(self, product_id: int) -> None:
        self.db.table("product_variants").delete().eq("product_id", product_id).execute()

    def update(self, product_id: int, data: dict):
        data = {k: v for k, v in data.items() if k != "variants"}
        if "stock" in data and data["stock"]:
            total_qty = sum(int(x) for x in data["stock"].values())
            data["quantity"] = total_qty
        res = self.db.table("products").update(data).eq("id", product_id).execute()
        return res.data[0] if res.data else None

    def delete(self, product_id: int):
        res = self.db.table("products").delete().eq("id", product_id).execute()
        return res.data

    def delete_storage_file(self, full_url: str):
        try:
            if not full_url or self.bucket not in full_url:
                return
            file_path = full_url.split(f"{self.bucket}/")[-1]
            self.db.storage.from_(self.bucket).remove([file_path])
        except Exception as e:
            print(f"Erro ao deletar imagem: {e}")
from shared.database import get_supabase_client

class PaymentRepository:
    def __init__(self):
        self.db = get_supabase_client()

    def get_product_price(self, product_id: int):
        res = self.db.table("products").select("id, price").eq("id", product_id).execute()
        return res.data[0] if res.data else None

    def get_product_price_and_stock(self, product_id: int):
        """Retorna id, price, stock e quantity para auditoria (fallback legado)."""
        res = self.db.table("products").select("id, price, stock, quantity").eq("id", product_id).execute()
        return res.data[0] if res.data else None

    def get_variant_stock(self, product_id: int, color: str, size: str):
        """Retorna a variante (product_id + color + size) para checagem de estoque."""
        color_val = (color or "").strip() or "Único"
        size_val = (size or "").strip() or "Único"
        res = (
            self.db.table("product_variants")
            .select("id, product_id, color, size, stock_quantity")
            .eq("product_id", product_id)
            .eq("color", color_val)
            .eq("size", size_val)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_product_full(self, product_id: int):
        """Retorna o produto completo para sincronizar com Firebase (formato legado)."""
        res = self.db.table("products").select("*").eq("id", product_id).execute()
        return res.data[0] if res.data else None

    def get_product_with_variants(self, product_id: int):
        """Retorna produto + variantes no formato consolidado para Firebase."""
        prod = self.get_product_full(product_id)
        if not prod:
            return None
        res = self.db.table("product_variants").select("color, size, stock_quantity").eq("product_id", product_id).execute()
        variants = [{"color": r["color"], "size": r["size"], "stock": int(r.get("stock_quantity", 0))} for r in (res.data or [])]
        price_raw = prod.get("price")
        price = float(price_raw) if price_raw is not None else 0.0
        images = prod.get("images") or []
        if not images and prod.get("image"):
            images = [prod["image"]]
        return {
            "id": str(product_id),
            "name": prod.get("name") or "",
            "description": prod.get("description") or "",
            "material": prod.get("material") or "",
            "print": prod.get("pattern") or "",
            "price": price,
            "image": prod.get("image") or "",
            "images": images,
            "variants": variants,
        }

    def create_order(self, payload, mp_response, total_amount):
        # 1. Cria o Pedido (Order)
        order_data = {
            "user_id": payload.user_id,
            "total_amount": total_amount,
            "status": mp_response.get("status"),
            "mp_payment_id": str(mp_response.get("id")),
            "payment_method": payload.payment_method_id,
            "installments": payload.installments
        }
        
        res_order = self.db.table("orders").insert(order_data).execute()
        
        if not res_order.data:
            raise Exception("Falha ao salvar pedido no banco.")
            
        order_id = res_order.data[0]["id"]

        items_data = []
        for item in payload.items:
            row = {
                "order_id": order_id,
                "product_id": item.id,
                "quantity": item.quantity,
                "product_name": item.name,
                "image_url": item.image,
                "price": item.price,
                "price_at_purchase": item.price,
            }
            if getattr(item, "color", None):
                row["color"] = item.color
            if getattr(item, "size", None):
                row["size"] = item.size
            items_data.append(row)
        
        # 3. Insere os Itens
        if items_data:
            self.db.table("order_items").insert(items_data).execute()
            
        return res_order.data[0]
    

    def update_stock(self, order_items):
        """
        Abate estoque por variante (product_id + color + size) em product_variants.
        Se não houver variante, fallback para products.stock (legado).
        """
        for item in order_items:
            try:
                prod_id = item.id
                sold_qty = item.quantity
                color_sold = (getattr(item, "color", None) or "").strip() or "Único"
                size_sold = (getattr(item, "size", None) or "").strip() or "Único"

                variant = self.get_variant_stock(prod_id, color_sold, size_sold)
                if variant:
                    new_qty = max(0, int(variant.get("stock_quantity", 0)) - sold_qty)
                    self.db.table("product_variants").update({"stock_quantity": new_qty}).eq("id", variant["id"]).execute()
                    total = self.db.table("product_variants").select("stock_quantity").eq("product_id", prod_id).execute()
                    new_product_qty = sum(int(r.get("stock_quantity", 0)) for r in (total.data or []))
                    self.db.table("products").update({"quantity": new_product_qty}).eq("id", prod_id).execute()
                else:
                    product = self.db.table("products").select("stock, quantity").eq("id", prod_id).execute()
                    if not product.data:
                        continue
                    current_stock = product.data[0].get("stock") or {}
                    if size_sold in current_stock:
                        current_stock[size_sold] = max(0, int(current_stock[size_sold]) - sold_qty)
                    elif "Único" in current_stock:
                        current_stock["Único"] = max(0, int(current_stock["Único"]) - sold_qty)
                    new_total = sum(int(v) for v in current_stock.values())
                    self.db.table("products").update({"stock": current_stock, "quantity": new_total}).eq("id", prod_id).execute()
            except Exception as e:
                print(f"Erro ao dar baixa no estoque do produto {item.id}: {e}")
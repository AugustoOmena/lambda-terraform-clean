from shared.database import get_supabase_client

class PaymentRepository:
    def __init__(self):
        self.db = get_supabase_client()

    def get_product_price(self, product_id: int):
        res = self.db.table("products").select("id, price").eq("id", product_id).execute()
        return res.data[0] if res.data else None

    def get_product_price_and_stock(self, product_id: int):
        """Retorna id, price, stock e quantity para auditoria de preço e checagem de estoque."""
        res = self.db.table("products").select("id, price, stock, quantity").eq("id", product_id).execute()
        return res.data[0] if res.data else None

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

        # 2. Prepara os Itens
        items_data = []
        for item in payload.items:
            items_data.append({
                "order_id": order_id,
                "product_id": item.id,
                "quantity": item.quantity,
                "product_name": item.name,
                "image_url": item.image,
                
                # --- O PULO DO GATO PARA CORRIGIR O ERRO ---
                # Enviamos com os dois nomes possíveis para satisfazer tabelas antigas e novas
                "price": item.price,            # <--- Satisfaz a coluna 'price' (Legado)
                "price_at_purchase": item.price # <--- Satisfaz a coluna 'price_at_purchase' (Nova)
            })
        
        # 3. Insere os Itens
        if items_data:
            self.db.table("order_items").insert(items_data).execute()
            
        return res_order.data[0]
    

    def update_stock(self, order_items):
        """
        Atualiza o estoque baseado nos itens vendidos.
        Desconta do JSON 'stock' e atualiza o total 'quantity'.
        """
        for item in order_items:
            try:
                prod_id = item.id
                sold_qty = item.quantity
                
                # O front deve mandar o tamanho escolhido. 
                # Se não mandou, assumimos "Único" (para produtos sem grade)
                # OBS: Precisamos garantir que 'size' venha no payload do item no Service
                size_sold = getattr(item, 'size', 'Único') 
                if not size_sold: 
                    size_sold = 'Único'

                # 1. Busca o produto atual
                product = self.db.table("products").select("stock, quantity").eq("id", prod_id).execute()
                if not product.data:
                    continue
                
                current_stock = product.data[0].get("stock") or {}
                
                # 2. Calcula novo estoque
                # Se o tamanho existe no JSON, subtrai.
                if size_sold in current_stock:
                    current_stock[size_sold] = max(0, int(current_stock[size_sold]) - sold_qty)
                else:
                    # Se não achou o tamanho exato, tenta descontar de "Único" ou ignora
                    if "Único" in current_stock:
                        current_stock["Único"] = max(0, int(current_stock["Único"]) - sold_qty)
                
                # Recalcula total para a vitrine
                new_total = sum(int(v) for v in current_stock.values())

                # 3. Salva
                self.db.table("products").update({
                    "stock": current_stock,
                    "quantity": new_total
                }).eq("id", prod_id).execute()

            except Exception as e:
                print(f"Erro ao dar baixa no estoque do produto {item.id}: {e}")
                # Não paramos o fluxo de venda por erro de estoque (melhor vender e resolver depois)
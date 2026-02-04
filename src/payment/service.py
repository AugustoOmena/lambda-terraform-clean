import mercadopago
import os
from decimal import Decimal, ROUND_HALF_UP

from shared.melhor_envio import MelhorEnvioAPIError, get_quote

from repository import PaymentRepository

# Pacote único padrão para cotação (alinhado ao frontend até haver dimensões por produto).
DEFAULT_WIDTH_CM = 16
DEFAULT_HEIGHT_CM = 12
DEFAULT_LENGTH_CM = 20
DEFAULT_WEIGHT_KG = 0.5
FREIGHT_TOLERANCE = Decimal("0.01")


class PaymentService:
    def __init__(self):
        self.repo = PaymentRepository()
        self.mp = mercadopago.SDK(os.environ.get("MP_ACCESS_TOKEN"))

    def process_payment(self, payload):
        # 0. Validação de frete: pacote único com soma das quantidades (igual ao frontend).
        total_qty = sum(item.quantity for item in payload.items)
        products = [
            {
                "width": DEFAULT_WIDTH_CM,
                "height": DEFAULT_HEIGHT_CM,
                "length": DEFAULT_LENGTH_CM,
                "weight": DEFAULT_WEIGHT_KG,
                "quantity": total_qty,
                "insurance_value": 0,
            }
        ]
        try:
            opcoes = get_quote(payload.cep, products)
        except MelhorEnvioAPIError as e:
            raise MelhorEnvioAPIError(f"Frete: não foi possível validar com a transportadora. {e}") from e
        if not opcoes:
            raise ValueError("Frete: nenhuma opção de frete disponível para o CEP informado.")
        frete_service = (payload.frete_service or "").strip()
        opcao_escolhida = next(
            (o for o in opcoes if o.get("service") and str(o["service"]).strip() == frete_service),
            None,
        )
        if not opcao_escolhida:
            raise ValueError(
                "Frete: serviço escolhido não encontrado na cotação. Recalcule o frete no checkout."
            )
        preco_opcao = Decimal(str(opcao_escolhida["preco"]))
        frete_enviado = Decimal(str(payload.frete)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if abs(frete_enviado - preco_opcao) > FREIGHT_TOLERANCE:
            raise ValueError(
                "Frete: valor enviado não confere com a cotação do serviço escolhido. Recalcule o frete no checkout."
            )

        # 1. Auditoria de Preços (Com Debug)
        total_calculado = Decimal('0.00')
        log_detalhado = [] # Vamos guardar o log de cada item para o erro
        
        # Verificação rápida: Lista vazia?
        if not payload.items:
             raise Exception(f"Erro: O backend recebeu uma lista de itens vazia. Front enviou R$ {payload.transaction_amount}")

        for item in payload.items:
            db_product = self.repo.get_product_price(item.id)
            
            if not db_product:
                raise Exception(f"Produto ID {item.id} não encontrado no banco.")
            
            # Conversão Segura
            db_price_raw = db_product.get('price', 0)
            if db_price_raw is None: db_price_raw = 0
            
            price = Decimal(str(db_price_raw))
            qty = Decimal(str(item.quantity))
            
            subtotal = price * qty
            total_calculado += subtotal
            
            # Adiciona ao log de debug
            log_detalhado.append(f"ID:{item.id} | Qtd:{qty} | PreçoDB:{price} | Sub:{subtotal}")

        # Arredonda
        total_calculado = total_calculado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_front = Decimal(str(payload.transaction_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        diff = abs(total_calculado - total_front)

        # SE DER ERRO, VAMOS MOSTRAR O PORQUÊ NA TELA
        if diff > Decimal('1.00'):
            debug_msg = " | ".join(log_detalhado)
            raise Exception(f"Divergência. Front: {total_front}, Back: {total_calculado}. Detalhes: {debug_msg}")

        # Se passou na auditoria, usamos o valor calculado pelo backend (Autoritativo)
        final_transaction_amount = float(total_calculado)

        # 2. Monta Payload MP
# 2. Monta o Payload do Mercado Pago
        payment_data = {
            "transaction_amount": final_transaction_amount,
            "description": f"Pedido Loja - {payload.payer.email}",
            "payment_method_id": payload.payment_method_id,
            "payer": {
                "email": payload.payer.email,
                "first_name": payload.payer.first_name,
                "last_name": payload.payer.last_name,
                "identification": {
                    "type": payload.payer.identification.type,
                    "number": payload.payer.identification.number
                }
            }
        }

        # NOVO: Se tiver endereço, adiciona ao payload
        if payload.payer.address:
            payment_data["payer"]["address"] = {
                "zip_code": payload.payer.address.zip_code,
                "street_name": payload.payer.address.street_name,
                "street_number": payload.payer.address.street_number,
                "neighborhood": payload.payer.address.neighborhood,
                "city": payload.payer.address.city,
                "federal_unit": payload.payer.address.federal_unit
            }

        # Ramificação de Métodos
        if payload.payment_method_id == "pix":
            payment_data["installments"] = 1
        elif "bol" in payload.payment_method_id or payload.payment_method_id == "pec":
            payment_data["installments"] = 1
        else: # Cartão
            if not payload.token:
                raise Exception("Token obrigatório para cartão.")
            payment_data["token"] = payload.token
            payment_data["installments"] = payload.installments
            if payload.issuer_id:
                payment_data["issuer_id"] = payload.issuer_id

        # 3. Envia MP
        request_options = mercadopago.config.RequestOptions()
        request_options.custom_headers = {
            'x-idempotency-key': f"{payload.user_id}-{final_transaction_amount}-{payload.payment_method_id}" 
        }

        payment_response = self.mp.payment().create(payment_data, request_options)
        response = payment_response["response"]

        if payment_response["status"] not in [200, 201]:
             error_msg = response.get('message', 'Erro MP')
             if 'cause' in response and response['cause']:
                 error_msg = f"{error_msg} - {response['cause'][0].get('description')}"
             raise Exception(error_msg)

        # 4. Salva Pedido
        order = self.repo.create_order(payload, response, final_transaction_amount)
        
        # 5. Baixa Estoque
        self.repo.update_stock(payload.items)

        # 6. Retorno
        result = {
            "id": response["id"],
            "status": response["status"],
            "status_detail": response["status_detail"],
            "order_db_id": order["id"],
            "payment_method_id": payload.payment_method_id
        }

        if payload.payment_method_id == "pix":
            poi = response.get("point_of_interaction", {}).get("transaction_data", {})
            result["qr_code"] = poi.get("qr_code")
            result["qr_code_base64"] = poi.get("qr_code_base64")
            result["ticket_url"] = poi.get("ticket_url")

        if "bol" in payload.payment_method_id or payload.payment_method_id == "pec":
            trans_det = response.get("transaction_details", {})
            result["ticket_url"] = trans_det.get("external_resource_url")

        return result
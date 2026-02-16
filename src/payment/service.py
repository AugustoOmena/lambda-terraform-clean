import mercadopago
import os
from decimal import Decimal, ROUND_HALF_UP

from aws_lambda_powertools import Logger
from shared.firebase import set_product_consolidated
from shared.melhor_envio import MelhorEnvioAPIError, get_quote

from repository import PaymentRepository

logger = Logger(service="payment")

# Pacote único padrão para cotação (alinhado ao frontend até haver dimensões por produto).
DEFAULT_WIDTH_CM = 16
DEFAULT_HEIGHT_CM = 12
DEFAULT_LENGTH_CM = 20
DEFAULT_WEIGHT_KG = Decimal("0.3")
FREIGHT_TOLERANCE = Decimal("0.15")


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
        frete_enviado = Decimal(str(payload.frete)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        frete_service_hint = (payload.frete_service or "").strip()

        opcao_escolhida = next(
            (o for o in opcoes if o.get("service") and str(o["service"]).strip() == frete_service_hint),
            None,
        )
        if opcao_escolhida:
            preco_opcao = Decimal(str(opcao_escolhida["preco"]))
            if abs(frete_enviado - preco_opcao) > FREIGHT_TOLERANCE:
                opcao_escolhida = None

        if not opcao_escolhida:
            opcao_por_preco = [
                o for o in opcoes
                if abs(frete_enviado - Decimal(str(o["preco"]))) <= FREIGHT_TOLERANCE
            ]
            if len(opcao_por_preco) == 1:
                opcao_escolhida = opcao_por_preco[0]
                logger.info(
                    "Frete: validado por preço (frete_service incorreto no frontend)",
                    extra={"frete_enviado": float(frete_enviado), "opcao": opcao_escolhida},
                )
            elif len(opcao_por_preco) > 1:
                opcao_escolhida = opcao_por_preco[0]
            else:
                raise ValueError(
                    "Frete: valor enviado não confere com nenhuma opção da cotação. Recalcule o frete no checkout."
                )

        # Fonte autoritativa: backend (Melhor Envio). Persistido no pedido para auditoria.
        shipping_service_canonical = (opcao_escolhida.get("service") or "").strip() or None
        shipping_amount_canonical = Decimal(str(opcao_escolhida["preco"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 1. Auditoria de Preços e checagem de estoque (Supabase)
        total_calculado = Decimal('0.00')
        log_detalhado = []

        if not payload.items:
            raise Exception(f"Erro: O backend recebeu uma lista de itens vazia. Front enviou R$ {payload.transaction_amount}")

        for item in payload.items:
            db_product = self.repo.get_product_price_and_stock(item.id)
            if not db_product:
                raise ValueError(f"Produto ID {item.id} não encontrado.")

            color = (getattr(item, "color", None) or "").strip() or "Único"
            size = (getattr(item, "size", None) or "").strip() or "Único"
            variant = self.repo.get_variant_stock(item.id, color, size)
            if variant:
                available = int(variant.get("stock_quantity", 0))
            else:
                stock = db_product.get("stock") or {}
                available = stock.get(size) if size in stock else stock.get("Único", 0)
                available = int(available) if available is not None else 0
            if available < item.quantity:
                raise ValueError(
                    f"O produto \"{item.name}\" está fora de estoque ou a quantidade solicitada não está disponível. "
                    f"Disponível: {available}, solicitado: {item.quantity}."
                )

            db_price_raw = db_product.get("price", 0)
            if db_price_raw is None:
                db_price_raw = 0
            price = Decimal(str(db_price_raw))
            qty = Decimal(str(item.quantity))
            subtotal = price * qty
            total_calculado += subtotal
            log_detalhado.append(f"ID:{item.id} | Qtd:{qty} | PreçoDB:{price} | Sub:{subtotal}")

        # Subtotal dos itens (preços do banco) e total esperado = subtotal + frete já validado
        total_calculado = total_calculado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_esperado = (total_calculado + frete_enviado).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_front = Decimal(str(payload.transaction_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        diff = abs(total_front - total_esperado)

        if diff > FREIGHT_TOLERANCE:
            debug_msg = " | ".join(log_detalhado)
            raise Exception(
                f"Divergência. Front (total com frete): {total_front}, Back (subtotal {total_calculado} + frete {frete_enviado} = {total_esperado}). Detalhes: {debug_msg}"
            )

        # Valor autoritativo: subtotal do backend + frete validado
        final_transaction_amount = float(total_esperado)

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

        # Se tiver endereço, adiciona ao payload (sem complement — MP não aceita)
        if payload.payer.address:
            addr = payload.payer.address
            payment_data["payer"]["address"] = {
                "zip_code": addr.zip_code,
                "street_name": addr.street_name,
                "street_number": addr.street_number,
                "neighborhood": addr.neighborhood,
                "city": addr.city,
                "federal_unit": addr.federal_unit,
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

        # 4. Extrai dados PIX/boleto para o usuário copiar depois
        payment_code = None
        payment_url = None
        payment_expiration = response.get("date_of_expiration")

        if payload.payment_method_id == "pix":
            poi = response.get("point_of_interaction", {}).get("transaction_data", {})
            payment_code = poi.get("qr_code")
        elif "bol" in payload.payment_method_id or payload.payment_method_id == "pec":
            trans = response.get("transaction_details", {})
            payment_url = trans.get("external_resource_url")

        # 5. Salva Pedido (shipping_service e shipping_amount vêm da cotação backend, não do front)
        order = self.repo.create_order(
            payload, response, final_transaction_amount,
            payment_code=payment_code,
            payment_url=payment_url,
            payment_expiration=payment_expiration,
            shipping_service=shipping_service_canonical,
            shipping_amount=float(shipping_amount_canonical),
        )
        
        # 6. Baixa Estoque
        self.repo.update_stock(payload.items)

        # 7. Sincroniza produtos vendidos no Firebase (formato consolidado com variantes)
        for product_id in {item.id for item in payload.items}:
            payload_fb = self.repo.get_product_with_variants(product_id)
            if payload_fb:
                set_product_consolidated(payload_fb)

        # 8. Retorno
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
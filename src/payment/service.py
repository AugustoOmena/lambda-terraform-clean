import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from aws_lambda_powertools import Logger
from shared.melhor_envio import MelhorEnvioAPIError, add_to_cart, get_quote

from exceptions import MercadoPagoAPIError, PaymentDeclinedError
from repository import PaymentRepository

logger = Logger(service="payment")

# Após HTTP 200/201 do MP, só estes status geram pedido + baixa de estoque.
_MP_STATUSES_PERSIST_ORDER = frozenset(
    {"approved", "pending", "in_process", "authorized"}
)

# Pacote único padrão para cotação (alinhado ao frontend até haver dimensões por produto).
DEFAULT_WIDTH_CM = 16
DEFAULT_HEIGHT_CM = 12
DEFAULT_LENGTH_CM = 20
DEFAULT_WEIGHT_KG = Decimal("0.3")
FREIGHT_TOLERANCE = Decimal("0.15")

# API Gateway HTTP API: integração Lambda costuma ter teto ~30s; a soma sequencial (frete + MP + DB + Firebase)
# não pode estourar isso; ajuste estes valores se o provedor for sistematicamente mais lento.
_PAYMENT_QUOTE_TIMEOUT_SEC = 8.0
_MP_CREATE_TIMEOUT_SEC = 16.0
_FIREBASE_SYNC_TIMEOUT_SEC = 5.0


class PaymentService:
    def __init__(self) -> None:
        self.repo = PaymentRepository()
        # Import tardio: SDK do Mercado Pago é pesado; OPTIONS no API Gateway não precisa carregar.
        import mercadopago as _mp

        self._mp = _mp
        self.mp: Any = _mp.SDK(os.environ.get("MP_ACCESS_TOKEN"))

    def process_payment(self, payload):
        # 0. Validação de frete: pacote único com soma das quantidades (igual ao frontend).
        t0 = time.perf_counter()

        def _log_stage(stage: str) -> None:
            logger.info(
                "payment_timing",
                extra={"stage": stage, "elapsed_ms": round((time.perf_counter() - t0) * 1000)},
            )

        total_qty = sum(item.quantity for item in payload.items)
        products = [
            {
                "width": DEFAULT_WIDTH_CM,
                "height": DEFAULT_HEIGHT_CM,
                "length": DEFAULT_LENGTH_CM,
                "weight": DEFAULT_WEIGHT_KG,
                "quantity": total_qty,
                "insurance_value": 1,
            }
        ]
        try:
            opcoes = get_quote(payload.cep, products, timeout_sec=_PAYMENT_QUOTE_TIMEOUT_SEC)
        except MelhorEnvioAPIError as e:
            raise MelhorEnvioAPIError(f"Frete: não foi possível validar com a transportadora. {e}") from e
        if not opcoes:
            raise ValueError("Frete: nenhuma opção de frete disponível para o CEP informado.")
        _log_stage("after_quote")
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
        _svc = opcao_escolhida.get("service")
        shipping_service_canonical = str(_svc).strip() if _svc is not None else None
        if shipping_service_canonical == "":
            shipping_service_canonical = None
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

        # 2. Monta Payload MP (first_name/last_name normalizados para compatibilidade com o checkout)
        first_name = (payload.payer.first_name or "").strip() or "Cliente"
        last_name = (payload.payer.last_name or "").strip() or "Desconhecido"
        payment_data = {
            "transaction_amount": final_transaction_amount,
            "description": f"Pedido Loja - {payload.payer.email}",
            "payment_method_id": payload.payment_method_id,
            "payer": {
                "email": payload.payer.email,
                "first_name": first_name,
                "last_name": last_name,
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

        # 3. Envia MP (timeout explícito: SDK pode bloquear além do teto do API Gateway ~30s)
        request_options = self._mp.config.RequestOptions()
        request_options.custom_headers = {
            'x-idempotency-key': f"{payload.user_id}-{final_transaction_amount}-{payload.payment_method_id}" 
        }

        def _mp_create() -> dict:
            return self.mp.payment().create(payment_data, request_options)

        # Não usar ``with ThreadPoolExecutor``: no __exit__ o shutdown espera todas as threads.
        # Se o SDK do MP bloquear além de ``result(timeout=...)``, a thread órfã faria a Lambda
        # esperar até o teto de 30s (API Gateway + timeout da função).
        pool_mp = ThreadPoolExecutor(max_workers=1)
        try:
            fut = pool_mp.submit(_mp_create)
            try:
                payment_response = fut.result(timeout=_MP_CREATE_TIMEOUT_SEC)
            except FuturesTimeout:
                logger.error(
                    "Mercado Pago: chamada excedeu o prazo; encerrando executor sem aguardar a thread",
                    extra={"timeout_sec": _MP_CREATE_TIMEOUT_SEC},
                )
                raise MercadoPagoAPIError(
                    "Timeout ao contatar Mercado Pago. Tente novamente em instantes.",
                    {},
                )
        finally:
            pool_mp.shutdown(wait=False)
        _log_stage("after_mp")
        response = payment_response["response"]
        if not isinstance(response, dict):
            response = {}

        http_st = payment_response.get("status")
        if http_st not in (200, 201):
            error_response = response
            print(f"Erro do Provedor: {error_response}")
            logger.error("Erro do provedor de pagamento", extra={"response": error_response})
            error_msg = error_response.get("message", "Erro MP")
            causes = error_response.get("cause") or []
            if causes:
                first_cause = causes[0] if isinstance(causes, list) else causes
                desc = first_cause.get("description", "") if isinstance(first_cause, dict) else str(first_cause)
                if desc:
                    error_msg = f"{error_msg} - {desc}"
            code = error_response.get("error") or error_response.get("code") or ""
            err_str = str(error_response).lower()
            if "invalid_parameter" in str(code).lower() or "invalid_parameter" in error_msg.lower():
                if "payer" in err_str or "first_name" in err_str or "last_name" in err_str or "name" in err_str:
                    raise ValueError(
                        "Nome do pagador inválido. Verifique first_name e last_name (evite caracteres especiais ou campos vazios)."
                    )
            raise MercadoPagoAPIError(error_msg, error_response)

        mp_pay_status = response.get("status")
        if mp_pay_status in ("rejected", "cancelled"):
            logger.warning(
                "Pagamento não aprovado pelo Mercado Pago",
                extra={
                    "payment_id": response.get("id"),
                    "mp_status": mp_pay_status,
                    "status_detail": response.get("status_detail"),
                },
            )
            raise PaymentDeclinedError(response)
        if mp_pay_status is not None and mp_pay_status not in _MP_STATUSES_PERSIST_ORDER:
            logger.warning(
                "Status de pagamento inesperado do Mercado Pago; não persistindo pedido",
                extra={
                    "payment_id": response.get("id"),
                    "mp_status": mp_pay_status,
                    "status_detail": response.get("status_detail"),
                },
            )
            raise PaymentDeclinedError(
                response,
                public_message="Não foi possível concluir o pagamento. Tente novamente ou use outro método.",
            )

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
        _log_stage("after_order")

        self._maybe_add_melhor_envio_cart(str(order["id"]), payload, opcao_escolhida)
        _log_stage("after_me_cart")

        # 6. Baixa Estoque
        self.repo.update_stock(payload.items)
        _log_stage("after_stock")

        # 7. Firebase: best-effort com teto; não pode bloquear a resposta (API Gateway ~30s total).
        def _firebase_sync() -> None:
            from shared.firebase import set_product_consolidated

            for product_id in {item.id for item in payload.items}:
                payload_fb = self.repo.get_product_with_variants(product_id)
                if payload_fb:
                    set_product_consolidated(payload_fb)

        pool_fb = ThreadPoolExecutor(max_workers=1)
        try:
            fut = pool_fb.submit(_firebase_sync)
            try:
                fut.result(timeout=_FIREBASE_SYNC_TIMEOUT_SEC)
            except FuturesTimeout:
                logger.error(
                    "Firebase sync excedeu o tempo; pedido já persistido no Supabase",
                    extra={"timeout_sec": _FIREBASE_SYNC_TIMEOUT_SEC},
                )
            except Exception as e:
                logger.exception("Firebase sync falhou: %s", e)
        finally:
            pool_fb.shutdown(wait=False)
        _log_stage("after_firebase")

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

    def _parse_me_sender_profile(self) -> Optional[dict[str, Any]]:
        raw = (os.environ.get("ME_SENDER_PROFILE") or "").strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("ME_SENDER_PROFILE não é JSON válido; carrinho ME ignorado")
            return None
        return parsed if isinstance(parsed, dict) else None

    def _build_me_recipient(self, payload: Any) -> Optional[dict[str, Any]]:
        addr = payload.payer.address
        if not addr:
            return None
        phone = (getattr(payload.payer, "phone", None) or "").strip()
        if not phone:
            phone = (os.environ.get("ME_DEFAULT_RECIPIENT_PHONE") or "").strip()
        if not phone:
            logger.info("Carrinho ME: telefone do destinatário ausente; defina payer.phone ou ME_DEFAULT_RECIPIENT_PHONE")
            return None
        name = f"{payload.payer.first_name or ''} {payload.payer.last_name or ''}".strip() or "Cliente"
        return {
            "name": name,
            "phone": phone,
            "email": payload.payer.email,
            "document": payload.payer.identification.number,
            "address": {
                "postal_code": addr.zip_code,
                "address": addr.street_name,
                "number": addr.street_number,
                "complement": (addr.complement or "")[:30] if addr.complement else "",
                "district": addr.neighborhood,
                "city": addr.city,
                "state_abbr": addr.federal_unit,
            },
        }

    def _maybe_add_melhor_envio_cart(
        self,
        order_id: str,
        payload: Any,
        opcao_escolhida: dict[str, Any],
    ) -> None:
        """Inclui a etiqueta no carrinho ME e persiste ``melhor_envio_order_id`` (não bloqueia o pagamento)."""
        sender = self._parse_me_sender_profile()
        recipient = self._build_me_recipient(payload)
        if not sender or not recipient:
            return
        svc_raw = opcao_escolhida.get("service")
        try:
            service_id = int(str(svc_raw).strip())
        except (TypeError, ValueError):
            logger.warning(
                "Carrinho ME: id do serviço não numérico; API de cotação deve retornar service inteiro",
                extra={"service": svc_raw},
            )
            return
        products = [
            {
                "name": item.name,
                "quantity": int(item.quantity),
                "unitary_value": float(item.price),
            }
            for item in payload.items
        ]
        total_qty = sum(int(item.quantity) for item in payload.items)
        volumes = [
            {
                "height": int(DEFAULT_HEIGHT_CM),
                "width": int(DEFAULT_WIDTH_CM),
                "length": int(DEFAULT_LENGTH_CM),
                "weight": round(float(DEFAULT_WEIGHT_KG) * max(1, total_qty), 3),
            }
        ]
        insurance = sum(float(item.price) * int(item.quantity) for item in payload.items)
        options = {
            "insurance_value": round(insurance, 2),
            "receipt": False,
            "own_hand": False,
        }
        try:
            cart_res = add_to_cart(
                service_id,
                sender,
                recipient,
                products,
                volumes,
                options=options,
            )
        except MelhorEnvioAPIError as e:
            logger.warning("Carrinho Melhor Envio falhou (pedido já criado)", extra={"err": str(e)})
            return
        me_oid = cart_res.get("id")
        if me_oid is None:
            logger.warning("Resposta do carrinho ME sem id", extra={"cart_res_keys": list(cart_res.keys())})
            return
        try:
            self.repo.update_melhor_envio_order_id(order_id, str(me_oid))
        except Exception as e:
            logger.exception("Falha ao persistir melhor_envio_order_id", extra={"order_id": order_id, "err": str(e)})
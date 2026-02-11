"""
Fulfillment service: business logic for Melhor Envio integration.

Handles cart insertion, checkout, label generation and webhook processing.
"""

import os
from aws_lambda_powertools import Logger

from shared.melhor_envio import (
    MelhorEnvioAPIError,
    add_to_cart,
    checkout_cart,
    generate_labels,
    get_tracking,
)
from repository import FulfillmentRepository
from schemas import CreateShipmentInput

logger = Logger(service="fulfillment")


class FulfillmentService:
    def __init__(self):
        self.repo = FulfillmentRepository()

    def create_shipment(self, order_id: str, payload: CreateShipmentInput) -> dict:
        """
        Cria etiqueta no carrinho Melhor Envio para um pedido.

        Args:
            order_id: ID do pedido no banco.
            payload: Dados com service_id escolhido.

        Returns:
            dict com melhor_envio_order_id e mensagem.

        Raises:
            ValueError: Pedido não encontrado ou sem endereço.
            MelhorEnvioAPIError: Erro na API Melhor Envio.
        """
        order = self.repo.get_order_for_shipment(order_id)
        if not order:
            raise ValueError(f"Pedido {order_id} não encontrado.")

        service_id = payload.service_id
        if service_id is None:
            raw = order.get("shipping_service")
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                raise ValueError("Pedido sem shipping_service. Não é possível criar etiqueta.")
            try:
                service_id = int(raw) if not isinstance(raw, int) else raw
            except (TypeError, ValueError):
                raise ValueError("shipping_service do pedido inválido para o Melhor Envio.")

        payer = order.get("payer") or {}
        address = payer.get("address")
        if not address:
            raise ValueError("Pedido não possui endereço de entrega.")

        cep_origem = os.environ.get("CEP_ORIGEM", "")
        sender_name = os.environ.get("SENDER_NAME", "Loja Omena")
        sender_phone = os.environ.get("SENDER_PHONE", "")
        sender_email = os.environ.get("SENDER_EMAIL", "")
        sender_document = os.environ.get("SENDER_DOCUMENT", "")
        sender_address = os.environ.get("SENDER_ADDRESS", "")
        sender_number = os.environ.get("SENDER_NUMBER", "")
        sender_neighborhood = os.environ.get("SENDER_NEIGHBORHOOD", "")
        sender_city = os.environ.get("SENDER_CITY", "")
        sender_state = os.environ.get("SENDER_STATE", "")

        sender = {
            "name": sender_name,
            "phone": sender_phone,
            "email": sender_email,
            "document": sender_document,
            "address": sender_address,
            "number": sender_number,
            "complement": "",
            "neighborhood": sender_neighborhood,
            "city": sender_city,
            "state_abbr": sender_state,
            "postal_code": cep_origem,
            "country_id": "BR",
        }

        recipient = {
            "name": payer.get("first_name", "Cliente") + " " + payer.get("last_name", ""),
            "phone": payer.get("phone", ""),
            "email": payer.get("email", ""),
            "document": (payer.get("identification") or {}).get("number", ""),
            "address": address.get("street_name", ""),
            "number": address.get("street_number", ""),
            "complement": address.get("complement", ""),
            "neighborhood": address.get("neighborhood", ""),
            "city": address.get("city", ""),
            "state_abbr": address.get("federal_unit", ""),
            "postal_code": address.get("zip_code", ""),
            "country_id": "BR",
        }

        items = order.get("items") or []
        products = [
            {
                "name": item.get("product_name", "Produto"),
                "quantity": item.get("quantity", 1),
                "unitary_value": float(item.get("price", 0)),
            }
            for item in items
        ]

        total_value = sum(p["unitary_value"] * p["quantity"] for p in products)
        volumes = [
            {
                "height": 12,
                "width": 16,
                "length": 20,
                "weight": 0.3,
            }
        ]

        options = {
            "insurance_value": total_value,
            "receipt": False,
            "own_hand": False,
        }

        result = add_to_cart(
            service_id=service_id,
            sender=sender,
            recipient=recipient,
            products=products,
            volumes=volumes,
            options=options,
        )

        me_order_id = result.get("id")
        if not me_order_id:
            raise MelhorEnvioAPIError(f"Melhor Envio não retornou ID: {result}")

        self.repo.update_melhor_envio_order_id(order_id, str(me_order_id))

        logger.info("Etiqueta criada no carrinho", extra={
            "order_id": order_id,
            "melhor_envio_order_id": me_order_id,
        })

        return {
            "melhor_envio_order_id": str(me_order_id),
            "message": "Etiqueta adicionada ao carrinho. Acesse o painel Melhor Envio para pagar.",
        }

    def process_webhook(self, event_type: str, data: dict) -> dict:
        """
        Processa evento de webhook do Melhor Envio.

        Args:
            event_type: Tipo do evento (ex: shipment.tracking, shipment.generated).
            data: Dados do evento.

        Returns:
            dict com resultado do processamento.
        """
        me_order_id = data.get("order_id") or data.get("id")
        if not me_order_id:
            logger.warning("Webhook sem order_id", extra={"event": event_type, "data": data})
            return {"status": "ignored", "reason": "no order_id"}

        order = self.repo.get_order_by_melhor_envio_id(str(me_order_id))
        if not order:
            logger.warning("Pedido não encontrado para ME order", extra={"me_order_id": me_order_id})
            return {"status": "ignored", "reason": "order not found"}

        order_id = order["id"]

        if event_type == "shipment.tracking":
            tracking_code = data.get("tracking") or data.get("tracking_code")
            if tracking_code:
                self.repo.update_tracking(
                    order_id=order_id,
                    tracking_code=tracking_code,
                    status="shipped",
                )
                logger.info("Rastreamento atualizado", extra={
                    "order_id": order_id,
                    "tracking_code": tracking_code,
                })
                return {"status": "updated", "tracking_code": tracking_code}

        elif event_type == "shipment.delivered":
            self.repo.update_order_status(order_id, "delivered")
            logger.info("Pedido entregue", extra={"order_id": order_id})
            return {"status": "delivered"}

        elif event_type == "shipment.canceled":
            logger.info("Envio cancelado no ME", extra={"order_id": order_id})
            return {"status": "canceled"}

        logger.info("Evento webhook não tratado", extra={"event": event_type})
        return {"status": "ignored", "reason": f"unhandled event: {event_type}"}

    def get_tracking_info(self, order_id: str) -> dict:
        """
        Consulta rastreamento de um pedido.

        Args:
            order_id: ID do pedido no banco.

        Returns:
            dict com tracking_code, status e eventos.
        """
        order = self.repo.get_order_for_shipment(order_id)
        if not order:
            raise ValueError(f"Pedido {order_id} não encontrado.")

        me_order_id = order.get("melhor_envio_order_id")
        if not me_order_id:
            return {
                "order_id": order_id,
                "tracking_code": order.get("tracking_code"),
                "status": order.get("status"),
                "tracking_events": [],
            }

        try:
            tracking_data = get_tracking([me_order_id])
            events = tracking_data.get(me_order_id, {}).get("tracking", {}).get("events", [])
        except MelhorEnvioAPIError:
            events = []

        return {
            "order_id": order_id,
            "tracking_code": order.get("tracking_code"),
            "status": order.get("status"),
            "tracking_events": events,
        }

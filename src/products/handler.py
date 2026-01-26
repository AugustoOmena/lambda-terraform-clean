from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import parse
from shared.responses import http_response
import json

from service import ProductService
from schemas import ProductInput, ProductUpdate

logger = Logger(service="products")

@logger.inject_lambda_context
def lambda_handler(event, context):
    try:
        method = event.get('requestContext', {}).get('http', {}).get('method')
        path_params = event.get('pathParameters') or {}
        query_params = event.get('queryStringParameters') or {}
        
        proxy_param = path_params.get('proxy') 
        product_id = path_params.get('id')

        if proxy_param and proxy_param.isdigit():
            product_id = proxy_param
        elif proxy_param == "exportar":
            product_id = None

        if product_id and "/" in str(product_id):
             product_id = str(product_id).split("/")[-1]

        if method == "OPTIONS":
            return http_response(200, {})

        service = ProductService()

        # --- GET ---
        if method == "GET":
            # Exportação CSV
            if proxy_param == "exportar":
                csv_content = service.export_products_csv()
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "text/csv; charset=utf-8",
                        "Content-Disposition": "attachment; filename=produtos.csv",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "body": csv_content,
                    "isBase64Encoded": False
                }

            # Get por ID
            if product_id and str(product_id).isdigit():
                return http_response(200, service.get_product(int(product_id)))
            
            # --- LISTAGEM COM FILTROS CORRIGIDA ---
            page = int(query_params.get("page", 1))
            limit = int(query_params.get("limit", 10))
            
            # Captura filtros (Correção aqui: aceita 'name' ou 'search')
            filters = {
                "name": query_params.get("name") or query_params.get("search"),
                "category": query_params.get("category"),
                "min_price": query_params.get("min_price"),
                "max_price": query_params.get("max_price"),
                "sort": query_params.get("sort", "newest"),
                "size": query_params.get("size") # Captura o tamanho (P, M, G...)
            }
            
            return http_response(200, service.list_products(page, limit, filters))

        # --- POST ---
        elif method == "POST":
            body = event.get("body")
            payload = parse(event=body, model=ProductInput)
            result = service.create_product(payload)
            return http_response(201, result)

        # --- PUT ---
        elif method == "PUT":
            body = event.get("body")
            payload = parse(event=body, model=ProductUpdate)
            
            if not product_id:
                try:
                    body_json = json.loads(body) if isinstance(body, str) else body
                    if isinstance(body_json, dict) and 'id' in body_json:
                        product_id = str(body_json['id'])
                except: pass

            if not product_id or not str(product_id).isdigit():
                return http_response(400, {"error": "ID obrigatório"})
            
            result = service.update_product(int(product_id), payload)
            return http_response(200, result)

        # --- DELETE ---
        elif method == "DELETE":
            if not product_id:
                raw_path = event.get('rawPath', '')
                if raw_path.split('/')[-1].isdigit():
                    product_id = raw_path.split('/')[-1]

            if not product_id or not str(product_id).isdigit():
                return http_response(400, {"error": "ID obrigatório"})
                
            service.delete_product(int(product_id))
            return http_response(204, {}) 

        return http_response(405, {"error": f"Método {method} não permitido"})

    except Exception as e:
        logger.exception("Erro crítico")
        return http_response(500, {"error": str(e)})
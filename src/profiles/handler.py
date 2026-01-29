from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.responses import http_response
from schemas import ProfileFilter, ProfileUpdate, ProfileDelete
from service import ProfileService

# Inicializa Logger estruturado
logger = Logger(service="profiles")


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext):
    """
    Handler para gerenciamento de perfis de usuários (Backoffice).
    
    Rotas:
    - GET /usuarios: Lista perfis com filtros e paginação
    - PUT /usuarios: Atualiza email/role de um perfil
    - DELETE /usuarios: Remove um perfil
    """
    method = event.get("requestContext", {}).get("http", {}).get("method")
    
    # CORS Preflight
    if method == "OPTIONS":
        return http_response(200, {})
    
    try:
        service = ProfileService()
        
        # GET: Listagem com filtros
        if method == "GET":
            # Extrai query parameters
            query_params = event.get("queryStringParameters") or {}
            
            # Valida e converte para ProfileFilter
            filters = ProfileFilter(
                page=int(query_params.get("page", 1)),
                limit=int(query_params.get("limit", 10)),
                email=query_params.get("email"),
                role=query_params.get("role"),
                sort=query_params.get("sort", "newest")
            )
            
            logger.info(f"Listando perfis: page={filters.page}, limit={filters.limit}")
            
            result = service.list_profiles(filters)
            return http_response(200, result)
        
        # PUT: Atualização de perfil
        elif method == "PUT":
            import json
            body = json.loads(event.get("body", "{}"))
            
            payload = ProfileUpdate(**body)
            logger.info(f"Atualizando perfil {payload.id}")
            
            updated = service.update_profile(payload)
            return http_response(200, updated)
        
        # DELETE: Remoção de perfil
        elif method == "DELETE":
            import json
            body = json.loads(event.get("body", "{}"))
            
            payload = ProfileDelete(**body)
            
            # Extrai user_id do contexto (se disponível, para validação)
            # Exemplo: event.get("requestContext", {}).get("authorizer", {}).get("sub")
            current_user_id = None  # TODO: Extrair do token JWT quando auth estiver implementado
            
            logger.info(f"Removendo perfil {payload.id}")
            
            result = service.delete_profile(payload, current_user_id)
            return http_response(200, result)
        
        else:
            return http_response(405, {"error": "Método não permitido"})
    
    except ValueError as e:
        # Erros de validação (Pydantic)
        logger.warning(f"Erro de validação: {str(e)}")
        return http_response(400, {"error": "Dados inválidos", "details": str(e)})
    
    except Exception as e:
        # Erros genéricos
        logger.exception("Erro crítico no processamento")
        return http_response(500, {"error": str(e)})

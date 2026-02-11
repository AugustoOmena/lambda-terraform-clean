import json
from decimal import Decimal
from datetime import datetime, date


class DecimalEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles Decimal, datetime, and date objects.
    
    Converts:
    - Decimal to float (or int if no decimal places)
    - datetime/date to ISO 8601 string
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, x-backoffice, X-Backoffice",
}

def http_response(status_code: int, body: dict) -> dict:
    headers = {"Content-Type": "application/json", **CORS_HEADERS}
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body, cls=DecimalEncoder)
    }


def options_response() -> dict:
    """Resposta para preflight CORS; inclui Max-Age para o browser poder cachear."""
    return {
        "statusCode": 200,
        "headers": {
            **CORS_HEADERS,
            "Access-Control-Max-Age": "86400",
            "Content-Type": "application/json",
        },
        "body": "{}"
    }
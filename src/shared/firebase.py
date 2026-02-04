import os
import json
import firebase_admin
from firebase_admin import credentials, db
from aws_lambda_powertools import Logger

logger = Logger(service="firebase")

_firebase_db = None


def get_firebase_db():
    """
    Initializes Firebase Admin SDK with service account credentials from environment variables.
    
    Returns singleton reference to Firebase Realtime Database.
    
    Raises:
        ValueError: If required environment variables are missing.
    """
    global _firebase_db
    
    if _firebase_db is not None:
        return _firebase_db
    
    try:
        firebase_admin.get_app()
        logger.info("Firebase Admin SDK already initialized (reusing existing app)")
    except ValueError:
        project_id = os.environ.get("FIREBASE_PROJECT_ID")
        client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
        private_key = os.environ.get("FIREBASE_PRIVATE_KEY")
        database_url = os.environ.get("FIREBASE_DATABASE_URL")
        melhor_envio_token = os.environ.get("MELHOR_ENVIO_TOKEN")
        cep_origem = os.environ.get("CEP_ORIGEM")
        
        if not all([project_id, client_email, private_key, database_url]):
            raise ValueError("Firebase credentials missing (ENV VARS)")
        
        private_key = private_key.replace('\\n', '\n')
        
        cred_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        try:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {
                'databaseURL': database_url
            })
            logger.info("Firebase Admin SDK initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            raise
    
    _firebase_db = db.reference()
    return _firebase_db

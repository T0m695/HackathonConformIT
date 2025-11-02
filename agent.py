import os
import json
from typing import List, Dict
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from database import load_events

class EventAgent:
    def __init__(self):
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_session_token = os.getenv("AWS_SESSION_TOKEN")
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("AWS credentials requises dans .env")
        
        session_config = {
            'region_name': self.aws_region,
            'aws_access_key_id': self.aws_access_key,
            'aws_secret_access_key': self.aws_secret_key,
        }
        
        if self.aws_session_token:
            session_config['aws_session_token'] = self.aws_session_token
        
        self.bedrock_runtime = boto3.client('bedrock-runtime', **session_config)
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"
        
        print("Chargement des données depuis PostgreSQL...")
        self.events = load_events()
        print(f"{len(self.events)} événements chargés")
    
    def search_events(self, user_query: str) -> str:
        if not self.events:
            return "Aucune donnée disponible. Vérifiez PostgreSQL."
        
        context = f"Voici {len(self.events)} événements:\n\n"
        for i, event in enumerate(self.events[:50], 1):
            context += f"Événement {i}:\n"
            context += f"- Titre: {event.get('titre', 'N/A')}\n"
            context += f"- Date: {event.get('date', 'N/A')}\n"
            context += f"- Lieu: {event.get('lieu', 'N/A')}\n\n"
        
        system_prompt = """Tu es un assistant spécialisé dans l'analyse des événements de sécurité.
Réponds en français avec des emojis appropriés."""
        
        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": f"{context}\n\nQuestion: {user_query}"}],
                    "temperature": 0.7
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text'] + f"\n\n📊 Total: {len(self.events)} événements"
            
        except Exception as e:
            return f"Erreur: {str(e)}"

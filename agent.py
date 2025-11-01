import os
import json
from typing import List, Dict, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from data_loader import load_events, format_event

class EventAgent:
    """Agent IA pour recommander des événements."""
    
    def __init__(self):
        """Initialise l'agent avec AWS Bedrock."""
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_session_token = os.getenv("AWS_SESSION_TOKEN")
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("❌ AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY sont requises")
        
        # Initialise le client Bedrock avec gestion d'erreurs
        try:
            session_config = {
                'service_name': 'bedrock-runtime',
                'region_name': self.aws_region,
                'aws_access_key_id': self.aws_access_key,
                'aws_secret_access_key': self.aws_secret_key,
            }
            
            # Ajouter le token de session seulement s'il existe
            if self.aws_session_token:
                session_config['aws_session_token'] = self.aws_session_token
                
            self.bedrock = boto3.client(**session_config)
            
        except Exception as e:
            raise ValueError(f"❌ Impossible d'initialiser le client AWS Bedrock: {str(e)}")
        
        # Charge les événements depuis la base de données
        print("🔍 DEBUG: Chargement des événements...")
        self.events = load_events()
        print(f"🔍 DEBUG: Événements chargés: {len(self.events)}")
        
        if self.events:
            print(f"🔍 DEBUG: Premier événement: {self.events[0]}")
        else:
            print("⚠️ DEBUG: Aucun événement chargé!")
            
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    def test_bedrock_connection(self) -> bool:
        """Test la connexion à AWS Bedrock."""
        try:
            # Test simple avec un prompt minimal
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Dis juste 'OK'"
                        }
                    ],
                    "temperature": 0.1
                })
            )
            
            response_body = json.loads(response['body'].read())
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'UnrecognizedClientException':
                print("🔑 Token de sécurité invalide ou expiré")
            elif error_code == 'AccessDeniedException':
                print("🚫 Accès refusé à Bedrock - vérifiez vos permissions")
            else:
                print(f"⚠️  Erreur AWS: {error_code}")
            return False
        except NoCredentialsError:
            print("🔑 Credentials AWS manquants")
            return False
        except Exception as e:
            print(f"❌ Erreur de connexion: {str(e)}")
            return False
    
    def create_context(self) -> str:
        """Crée le contexte avec tous les événements."""
        context = "Liste des événements disponibles:\n\n"
        for i, event in enumerate(self.events, 1):
            context += f"Événement {i}:{format_event(event)}\n"
        return context
    
    def search_events(self, user_query: str) -> str:
        """Recherche des événements basés sur la requête utilisateur."""
        if not self.events:
            return "❌ Aucun événement disponible dans la base de données."
        
        context = self.create_context()
        
        system_prompt = """Tu es un assistant intelligent spécialisé dans la recommandation d'événements.
Tu dois aider les utilisateurs à trouver des événements qui correspondent à leurs intérêts.
Base tes recommandations uniquement sur les événements fournis dans le contexte.
Réponds de manière claire et concise en français avec des emojis appropriés."""
        
        try:
            message = f"{context}\n\nQuestion: {user_query}"
            
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "system": system_prompt,
                    "messages": [
                        {
                            "role": "user",
                            "content": message
                        }
                    ],
                    "temperature": 0.7
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'UnrecognizedClientException':
                return "🔑 ❌ Token de sécurité expiré. Veuillez renouveler vos credentials AWS avec 'aws sts get-session-token'"
            elif error_code == 'AccessDeniedException':
                return "🚫 ❌ Accès refusé à Bedrock. Vérifiez vos permissions IAM."
            elif error_code == 'ValidationException':
                return "⚠️ ❌ Erreur de validation du modèle. Le modèle Claude 3 Haiku est-il disponible dans votre région?"
            else:
                return f"⚠️ ❌ Erreur AWS ({error_code}): {str(e)}"
        except Exception as e:
            return f"❌ Erreur lors de la recherche: {str(e)}"
    
    def get_all_categories(self) -> List[str]:
        """Retourne toutes les catégories d'événements."""
        categories = set()
        for event in self.events:
            if 'categorie' in event:
                categories.add(event['categorie'])
        return sorted(list(categories))

"""
Fonction pour analyser des résultats SQL avec AWS Bedrock
"""
import os
import json
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()


def query_with_ai(sql_results, user_prompt: str) -> str:
    """
    Prend un résultat de requête SQL et un prompt utilisateur,
    utilise AWS Bedrock pour générer une réponse intelligente.
    
    Args:
        sql_results: Résultats SQL - peut être:
            - Liste de dictionnaires: [{"id": 1, "name": "test"}, ...]
            - String: "résultat de la requête"
        user_prompt: Question ou prompt de l'utilisateur
        
    Returns:
        str: Réponse générée par l'IA
"""
    
    # Récupérer les credentials AWS depuis .env
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    if not aws_access_key or not aws_secret_key:
        return " Erreur: AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY requis dans .env"
    
    # Initialiser le client AWS Bedrock
    try:
        session_config = {
            'region_name': aws_region,
            'aws_access_key_id': aws_access_key,
            'aws_secret_access_key': aws_secret_key,
        }
        
        if aws_session_token:
            session_config['aws_session_token'] = aws_session_token
        
        bedrock_runtime = boto3.client('bedrock-runtime', **session_config)
        
    except Exception as e:
        return f" Erreur lors de l'initialisation AWS Bedrock: {str(e)}"
    
    if sql_results is None or sql_results == "":
        context = "Aucun résultat trouvé dans la base de données."
    
    # Si c'est une string simple
    elif isinstance(sql_results, str):
        context = f"Résultat de la requête SQL:\n{sql_results}"
    
    # Autre type (dict unique, tuple, etc.)
    else:
        context = f"Résultat de la requête SQL:\n{str(sql_results)}"
    
    # Prompt système
    system_prompt = """Tu es un assistant intelligent spécialisé dans l'analyse de données.
Tu reçois des résultats de requêtes SQL et tu dois aider l'utilisateur à comprendre et analyser ces données.
Réponds de manière claire, précise et structurée en français. Ta réponse doit être conscise et aller droit au but.
Si tu dois faire des calculs ou des statistiques, sois précis."""
    
    # Construire le message complet
    user_message = f"""Contexte des données:
{context}

Question de l'utilisateur:
{user_prompt}

Analyse les données ci-dessus et réponds à la question de l'utilisateur."""
    
    # Appeler AWS Bedrock Claude 3 Haiku

    response = bedrock_runtime.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "temperature": 0.3
        })
    )
    
    response_body = json.loads(response['body'].read())
    ai_response = response_body['content'][0]['text']
    

    if isinstance(sql_results, list):
        nb_results = len(sql_results)
    elif isinstance(sql_results, (str, int, float)):
        nb_results = 1
    else:
        nb_results = "N/A"

    return ai_response

# Exemple d'utilisation
if __name__ == "__main__":

    prompt1 = "Donne moi le nombre de Production Operator"
    reponse1 = query_with_ai(output_sql, prompt1)
    print(f" Prompt: {prompt1}")
    print(f"\n Réponse:\n{reponse1}\n")
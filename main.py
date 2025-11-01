import os
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Ajout d'une constante pour les modèles d'embedding courants
# Vous devez activer l'accès à ce modèle dans la console AWS Bedrock.
TITAN_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v1" 

def _get_bedrock_client(aws_region: str, aws_access_key: str, aws_secret_key: str, aws_session_token: str = None):
    """
    Fonction utilitaire pour initialiser le client Bedrock Runtime.
    """
    session_config = {
        'service_name': 'bedrock-runtime',
        'region_name': aws_region,
        'aws_access_key_id': aws_access_key,
        'aws_secret_access_key': aws_secret_key,
    }
    
    if aws_session_token:
        session_config['aws_session_token'] = aws_session_token
        
    return boto3.client(**session_config)

def invoke_llm(prompt_text: str, model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"):
    """
    Appelle un modèle LLM sur Amazon Bedrock avec le prompt donné.
    
    Args:
        prompt_text (str): Le texte de la requête utilisateur.
        model_id (str): L'ID du modèle Bedrock à utiliser (par défaut: Claude 3 Haiku).

    Returns:
        str: Le texte généré par le LLM ou un message d'erreur.
    """
    
    # --- Configuration AWS ---
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN") # Optionnel pour les sessions temporaires
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    if not aws_access_key or not aws_secret_key:
        return "❌ ERREUR: Les variables d'environnement AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY sont requises."

    # --- Initialisation du client Bedrock ---
    try:
        bedrock = _get_bedrock_client(aws_region, aws_access_key, aws_secret_key, aws_session_token)
        print(f"✅ Client Bedrock initialisé (Région: {aws_region}, Modèle LLM: {model_id})")

    except Exception as e:
        return f"❌ ERREUR: Impossible d'initialiser le client AWS Bedrock: {str(e)}"

    # --- Préparation du corps de la requête (Format pour les modèles Anthropic Claude) ---
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": prompt_text
            }
        ],
        "temperature": 0.5
    })
    
    # --- Appel de l'API ---
    try:
        print("🔍 Appel de l'API Bedrock LLM en cours...")
        response = bedrock.invoke_model(
            modelId=model_id,
            body=body
        )
        
        # --- Traitement de la réponse ---
        response_body = json.loads(response['body'].read())
        
        if response_body and 'content' in response_body and response_body['content']:
            return response_body['content'][0]['text']
        else:
            return "⚠️ Réponse vide du modèle LLM."
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        return f"❌ ERREUR AWS ({error_code}): {str(e)}"
    except Exception as e:
        return f"❌ ERREUR lors de l'appel au modèle LLM: {str(e)}"


def invoke_embedding_model(text_to_embed: str, model_id: str = TITAN_EMBEDDING_MODEL_ID):
    """
    Appelle un modèle d'embedding sur Amazon Bedrock pour obtenir un vecteur.
    
    Args:
        text_to_embed (str): Le texte à convertir en embedding.
        model_id (str): L'ID du modèle d'embedding (par défaut: Titan G1 Text).

    Returns:
        list: Le vecteur d'embedding (liste de flottants) ou un message d'erreur.
    """
    
    # --- Configuration AWS ---
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    if not aws_access_key or not aws_secret_key:
        return "❌ ERREUR: Les variables d'environnement AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY sont requises."

    # --- Initialisation du client Bedrock ---
    try:
        bedrock = _get_bedrock_client(aws_region, aws_access_key, aws_secret_key, aws_session_token)
        print(f"✅ Client Bedrock initialisé (Région: {aws_region}, Modèle Embedding: {model_id})")

    except Exception as e:
        return f"❌ ERREUR: Impossible d'initialiser le client AWS Bedrock: {str(e)}"

    # --- Préparation du corps de la requête (Format pour Amazon Titan Text Embeddings) ---
    # Le format varie selon le modèle (ex: Cohere utilise 'texts' au lieu de 'inputText')
    body = json.dumps({
        "inputText": text_to_embed
    })
    
    # --- Appel de l'API ---
    try:
        print(f"🔍 Génération de l'embedding pour le texte: '{text_to_embed[:50]}...'")
        response = bedrock.invoke_model(
            modelId=model_id,
            body=body,
            contentType='application/json',
            accept='application/json'
        )
        
        # --- Traitement de la réponse ---
        response_body = json.loads(response['body'].read())
        
        # Extrait l'embedding (liste de flottants)
        if response_body and 'embedding' in response_body:
            return response_body['embedding']
        else:
            return "⚠️ Réponse vide ou format incorrect du modèle d'embedding."
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        return f"❌ ERREUR AWS ({error_code}): {str(e)}"
    except Exception as e:
        return f"❌ ERREUR lors de l'appel au modèle d'embedding: {str(e)}"

if __name__ == "__main__":
    
    load_dotenv()
    
    # 1. Définissez votre prompt ici
    llm_prompt = "Donne un code python pour diagonaliser une matrice numpy."
    embedding_text = "Quel est le produit le plus populaire en vente?"

    print(f"\n--- Requête LLM Minimaliste ---")
    print(f"Prompt: '{llm_prompt}'")
    
    # 2. Appelez la fonction LLM et affichez la réponse
    llm_response = invoke_llm(llm_prompt)
    
    print("\n--- Réponse du LLM ---")
    print(llm_response)
    print("-------------------------\n")
    
    # 3. Appel de la nouvelle fonction d'Embedding
    print(f"\n--- Calcul de l'Embedding ---")
    print(f"Texte à embédir: '{embedding_text}'")
    
    embedding_vector = invoke_embedding_model(embedding_text)
    
    print("\n--- Résultat de l'Embedding ---")
    if isinstance(embedding_vector, list):
        print(f"✅ Vecteur d'embedding généré. Dimension: {len(embedding_vector)}")
        print(f"Exemple des 5 premières valeurs: {embedding_vector[:5]}")
    else:
        print(embedding_vector) # Affiche le message d'erreur
    print("-----------------------------\n")
import boto3
import json

# Initialisez le client Bedrock (à faire en dehors de la fonction Lambda pour la performance)
bedrock_client = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')

def decompose_prompt_for_sql(user_prompt: str, schema: str) -> list:
    """
    Prend un prompt utilisateur et le décompose en sous-questions simples.
    'schema' est la description de vos tables SQL (ex: CREATE TABLE ...)
    """
    
    # Un modèle rapide et peu coûteux est parfait pour cela
    model_id = "anthropic.claude-3-haiku-20240307-v1:0" 

    # Ce prompt est crucial. Il utilise le "few-shot learning".
    system_prompt = f"""
    Vous êtes un expert en analyse de données. Votre tâche est de décomposer une question utilisateur 
    (potentiellement complexe) en une ou plusieurs sous-questions simples et indépendantes. 
    Chaque sous-question doit être directement traduisible en UNE SEULE requête SQL simple.
    
    Prenez en compte ce schéma de base de données :
    <schema>
    {schema}
    </schema>
    
    Répondez TOUJOURS au format JSON : {{"sub_queries": ["question 1", "question 2", ...]}}

    EXEMPLE 1 :
    Question: "Quel est le total des ventes ?"
    Réponse: {{"sub_queries": ["Quel est le total des ventes ?"]}}

    EXEMPLE 2 :
    Question: "Compare le CA en France et en Allemagne."
    Réponse: {{"sub_queries": ["Quel est le CA total pour la France ?", "Quel est le CA total pour l'Allemagne ?"]}}

    EXEMPLE 3 :
    Question: "Montre les ventes de 'Produit A' et le top 3 des clients en Espagne."
    Réponse: {{"sub_queries": ["Quelles sont les ventes totales pour 'Produit A' ?", "Quels sont les 3 meilleurs clients en Espagne ?"]}}
    """
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": f"Question: \"{user_prompt}\""
            }
        ]
    }

    try:
        response = bedrock_client.invoke_model(
            body=json.dumps(request_body),
            modelId=model_id,
        )
        
        response_body = json.loads(response.get('body').read())
        # Extrait le texte JSON de la réponse du modèle
        json_text = response_body['content'][0]['text']
        
        # Parse le JSON pour obtenir la liste
        result = json.loads(json_text)
        return result['sub_queries']

    except Exception as e:
        print(f"Erreur lors de l'appel à Bedrock : {e}")
        # En cas d'échec, retournez le prompt original dans une liste
        return [user_prompt]

# --- Utilisation ---
votre_schema_sql = "CREATE TABLE sales (id INT, country VARCHAR, amount INT, product VARCHAR, salesperson VARCHAR); ..."
question_complexe = "Compare le CA en France et en Allemagne pour le T1, et donne-moi aussi les 3 meilleurs vendeurs pour la France."

sub_queries = decompose_prompt_for_sql(question_complexe, votre_schema_sql)
print(sub_queries)
# Sortie attendue (exemple) :
# [
#   "Quel est le chiffre d'affaires total pour la France au T1 ?",
#   "Quel est le chiffre d'affaires total pour l'Allemagne au T1 ?",
#   "Quels sont les 3 meilleurs vendeurs en France ?"
# ]
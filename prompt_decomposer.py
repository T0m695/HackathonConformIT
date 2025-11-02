"""
Décomposeur de prompts complexes avec AWS Bedrock
"""
import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()


def is_complex_prompt(prompt: str) -> bool:
    """Détecte si un prompt est complexe (multi-questions, multi-tâches)"""
    indicators = [
        ' et ', ' puis ', ' ensuite ', ' également ', ' aussi ',
        '?', 'combien', 'quels', 'comment', 'pourquoi',
        'compare', 'analyse', 'résume', 'liste'
    ]
    
    prompt_lower = prompt.lower()
    complexity_score = sum(1 for ind in indicators if ind in prompt_lower)
    
    return complexity_score >= 3 or prompt.count('?') > 1 or len(prompt.split()) > 30


def convert_to_sql_query(prompt: str) -> str:
    """Convertit un prompt simple en requête SQL via AWS Bedrock"""
    
    aws_config = {
        'region_name': os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY"),
    }
    
    if token := os.getenv("AWS_SESSION_TOKEN"):
        aws_config['aws_session_token'] = token
    
    bedrock = boto3.client('bedrock-runtime', **aws_config)
    
    system_prompt = """Tu es un expert SQL. Convertis les questions en requêtes SQL PostgreSQL.
Tables disponibles: corrective_measure(measure_id, name, description, implementation_date, cost, organizational_unit_id), event(event_id, title, date, location), person(person_id, name, role), organizational_unit(unit_id, name), risk(risk_id, severity, description).
Réponds UNIQUEMENT avec la requête SQL, sans explication."""
    
    user_message = f"""Question: {prompt}

Génère la requête SQL PostgreSQL correspondante."""
    
    try:
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
                "temperature": 0.1
            })
        )
        
        response_body = json.loads(response['body'].read())
        sql_query = response_body['content'][0]['text'].strip()
        
        if 'SELECT' in sql_query.upper():
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            return sql_query
        
        return None
        
    except Exception as e:
        print(f"Erreur conversion SQL: {e}")
        return None


def decompose_prompt(prompt: str) -> list:
    """Décompose un prompt complexe en sous-prompts simples via AWS Bedrock"""
    
    aws_config = {
        'region_name': os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY"),
    }
    
    if token := os.getenv("AWS_SESSION_TOKEN"):
        aws_config['aws_session_token'] = token
    
    bedrock = boto3.client('bedrock-runtime', **aws_config)
    
    system_prompt = """Tu es un expert en décomposition de questions.
Décompose la question complexe en sous-questions simples et indépendantes pour générer des requêtes SQL.
Réponds UNIQUEMENT avec une liste JSON de sous-questions, sans explication."""
    
    user_message = f"""Question complexe à décomposer:
"{prompt}"

Retourne un JSON avec cette structure:
{{"sub_prompts": ["question 1", "question 2", ...]}}"""
    
    try:
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
                "temperature": 0.3
            })
        )
        
        response_body = json.loads(response['body'].read())
        ai_text = response_body['content'][0]['text']
        
        # Extraire le JSON de la réponse
        if '{' in ai_text and '}' in ai_text:
            json_start = ai_text.index('{')
            json_end = ai_text.rindex('}') + 1
            result = json.loads(ai_text[json_start:json_end])
            return result.get('sub_prompts', [prompt])
        
        return [prompt]
        
    except Exception as e:
        print(f"Erreur décomposition: {e}")
        return [prompt]


def process_prompt(prompt: str):
    """Point d'entrée: détecte complexité et retourne requêtes SQL ou sous-prompts"""
    
    if is_complex_prompt(prompt):
        print(f"🔍 Prompt complexe détecté")
        sub_prompts = decompose_prompt(prompt)
        print(f"📊 Décomposé en {len(sub_prompts)} sous-prompts")
        
        sql_queries = []
        for sub_prompt in sub_prompts:
            sql = convert_to_sql_query(sub_prompt)
            if sql:
                sql_queries.append({"prompt": sub_prompt, "sql": sql})
        
        return sql_queries
    else:
        print(f"✅ Prompt simple")
        sql = convert_to_sql_query(prompt)
        
        if sql:
            return [{"prompt": prompt, "sql": sql}]
        else:
            return [{"prompt": prompt, "sql": None}]


if __name__ == "__main__":
    # Test avec prompt simple
    simple = "Combien de mesures correctives en 2024?"
    print(f"Test 1: {simple}")
    result1 = process_prompt(simple)
    print(f"Résultat: {result1[0]['sql']}\n")
    
    # Test avec prompt complexe
    complex = "Compte les incidents de 2024, compare avec 2023, et liste les unités avec le plus de mesures"
    print(f"Test 2: {complex}")
    result2 = process_prompt(complex)
    for i, r in enumerate(result2, 1):
        print(f"{i}. {r['prompt']}")
        print(f"   SQL: {r['sql']}\n")

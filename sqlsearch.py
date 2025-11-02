import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()


def sqlsearch(prompt: str) -> str:
    aws_config = {
        'region_name': os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY"),
    }
    
    if token := os.getenv("AWS_SESSION_TOKEN"):
        aws_config['aws_session_token'] = token
    
    bedrock = boto3.client('bedrock-runtime', **aws_config)
    
    system_prompt = """Tu es un expert SQL. Convertis les questions en requêtes SQL PostgreSQL.
Tables: corrective_measure(measure_id, name, description, implementation_date, cost, organizational_unit_id), event(event_id, title, date, location), person(person_id, name, role), organizational_unit(unit_id, name), risk(risk_id, severity, description).
Réponds UNIQUEMENT avec la requête SQL."""
    
    try:
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "system": system_prompt,
                "messages": [{"role": "user", "content": f"Question: {prompt}\n\nGénère la requête SQL PostgreSQL."}],
                "temperature": 0.1
            })
        )
        
        response_body = json.loads(response['body'].read())
        sql_query = response_body['content'][0]['text'].strip()
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        return sql_query
        
    except Exception as e:
        return f"Erreur: {str(e)}"

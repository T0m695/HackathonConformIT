# bedrock_utils.py
import os
import json
import boto3
import time
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.embeddings import Embeddings

from .config import Config, debug_print

def _get_bedrock_client():
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    access = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    token = os.getenv("AWS_SESSION_TOKEN")

    if not access or not secret:
        raise RuntimeError("AWS credentials missing in .env")

    cfg = {
        "service_name": "bedrock-runtime",
        "region_name": region,
        "aws_access_key_id": access,
        "aws_secret_access_key": secret,
    }
    if token:
        cfg["aws_session_token"] = token
    return boto3.client(**cfg)

def invoke_llm(prompt: str, model_id: str = Config.CLAUDE_MODEL) -> str:
    try:
        client = _get_bedrock_client()
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}]
        })
        resp = client.invoke_model(modelId=model_id, body=body)
        out = json.loads(resp["body"].read())
        return out["content"][0]["text"]
    except Exception as e:
        debug_print(f"❌ LLM invocation failed: {e}")
        return f"LLM error: {e}"

def invoke_embedding(text: str, model_id: str = Config.TITAN_EMBED_MODEL) -> List[float]:
    try:
        client = _get_bedrock_client()
        body = json.dumps({"inputText": text})
        resp = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        out = json.loads(resp["body"].read())
        if "embedding" not in out:
            raise ValueError(f"Bad embedding response: {out}")
        return out["embedding"]
    except Exception as e:
        raise RuntimeError(f"Embedding failed: {e}")

def invoke_embeddings_batch(
    texts: List[str], 
    model_id: str = Config.TITAN_EMBED_MODEL,
    max_workers: int = 10,
    retry_count: int = 3,
    delay_between_batches: float = 0.1
) -> List[List[float]]:
    """
    Génère les embeddings en parallèle avec retry et rate limiting
    
    Args:
        texts: Liste des textes à encoder
        model_id: Modèle Bedrock à utiliser
        max_workers: Nombre de threads parallèles (recommandé: 5-15)
        retry_count: Nombre de tentatives en cas d'erreur
        delay_between_batches: Délai en secondes entre les requêtes (rate limiting)
    
    Returns:
        Liste des embeddings (même ordre que texts)
    """
    client = _get_bedrock_client()
    results = [None] * len(texts)
    errors = []
    
    def generate_single(idx: int, text: str) -> tuple:
        """Génère un embedding avec retry"""
        for attempt in range(retry_count):
            try:
                # Rate limiting basique
                if delay_between_batches > 0:
                    time.sleep(delay_between_batches)
                
                body = json.dumps({"inputText": text[:5000]})  # Limiter la taille
                resp = client.invoke_model(
                    modelId=model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                out = json.loads(resp["body"].read())
                
                if "embedding" not in out:
                    raise ValueError(f"Bad embedding response: {out}")
                
                return (idx, out["embedding"], None)
            
            except Exception as e:
                if attempt == retry_count - 1:
                    return (idx, None, str(e))
                
                # Backoff exponentiel
                wait_time = (2 ** attempt) * 0.5
                time.sleep(wait_time)
        
        return (idx, None, "Max retries exceeded")
    
    # Exécution parallèle
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(generate_single, i, text): i 
            for i, text in enumerate(texts)
        }
        
        completed = 0
        total = len(texts)
        
        for future in as_completed(futures):
            completed += 1
            idx, embedding, error = future.result()
            
            if embedding:
                results[idx] = embedding
            else:
                errors.append((idx, error))
                debug_print(f"❌ Failed to generate embedding for text {idx}: {error}")
            
            # Progress
            if completed % 10 == 0 or completed == total:
                debug_print(f"📊 Progress: {completed}/{total} embeddings generated")
    
    # Vérifier les résultats
    failed_count = sum(1 for r in results if r is None)
    if failed_count > 0:
        debug_print(f"⚠️ {failed_count}/{total} embeddings failed to generate")
    
    return results

class BedrockEmbeddings(Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Utilise le batch pour les documents"""
        return invoke_embeddings_batch(texts, max_workers=10)

    def embed_query(self, text: str) -> List[float]:
        """Requête unique - pas de batch"""
        return invoke_embedding(text)
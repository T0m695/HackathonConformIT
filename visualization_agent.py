import os
import json
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from database import get_connection
import psycopg2.extras

class VisualizationAgent:
    """Agent IA pour générer des visualisations de données."""
    
    def __init__(self):
        """Initialise l'agent avec AWS Bedrock."""
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_session_token = os.getenv("AWS_SESSION_TOKEN")
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("❌ AWS credentials requises")
        
        try:
            session_config = {
                'service_name': 'bedrock-runtime',
                'region_name': self.aws_region,
                'aws_access_key_id': self.aws_access_key,
                'aws_secret_access_key': self.aws_secret_key,
            }
            
            if self.aws_session_token:
                session_config['aws_session_token'] = self.aws_session_token
                
            self.bedrock = boto3.client(**session_config)
            
        except Exception as e:
            raise ValueError(f"❌ Impossible d'initialiser le client AWS Bedrock: {str(e)}")
            
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"
        print("✅ Agent de visualisation initialisé")
    
    def analyze_query(self, user_query: str) -> Dict:
        """Analyse la requête utilisateur pour déterminer le type de visualisation."""
        
        system_prompt = """Tu es un assistant spécialisé dans l'analyse de données de sécurité industrielle.
Analyse la requête de l'utilisateur et détermine:
1. Le type de graphique approprié (bar, line, pie, doughnut, scatter)
2. Les données à afficher
3. Le titre du graphique
4. Les filtres à appliquer

Réponds UNIQUEMENT avec un JSON valide au format suivant:
{
    "chart_type": "bar|line|pie|doughnut|scatter",
    "data_source": "events_by_category|events_by_month|events_by_severity|events_by_location|measures_by_cost",
    "title": "Titre du graphique",
    "filters": {
        "duration": 12,
        "category": null,
        "severity": null
    },
    "description": "Description courte"
}"""
        
        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "system": system_prompt,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Analyse cette requête: {user_query}"
                        }
                    ],
                    "temperature": 0.3
                })
            )
            
            response_body = json.loads(response['body'].read())
            ai_response = response_body['content'][0]['text']
            
            # Extraire le JSON de la réponse
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                return json.loads(ai_response[json_start:json_end])
            else:
                return None
                
        except Exception as e:
            print(f"❌ Erreur analyse: {e}")
            return None
    
    def get_data_for_visualization(self, data_source: str, filters: Dict) -> Dict:
        """Récupère les données depuis la base de données."""
        try:
            conn = get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if data_source == "events_by_category":
                cursor.execute("""
                    SELECT 
                        e.type as label,
                        COUNT(*) as value
                    FROM event e
                    WHERE e.type IS NOT NULL
                    GROUP BY e.type
                    ORDER BY value DESC
                    LIMIT 10
                """)
                
            elif data_source == "events_by_month":
                duration = filters.get('duration', 12)
                if duration >= 999:
                    cursor.execute("""
                        SELECT 
                            TO_CHAR(e.start_datetime, 'YYYY-MM') as label,
                            COUNT(*) as value
                        FROM event e
                        WHERE e.start_datetime IS NOT NULL
                        GROUP BY TO_CHAR(e.start_datetime, 'YYYY-MM')
                        ORDER BY label DESC
                        LIMIT 24
                    """)
                else:
                    cursor.execute("""
                        WITH months AS (
                            SELECT TO_CHAR(
                                CURRENT_DATE - INTERVAL '1 month' * generate_series(0, %s - 1),
                                'YYYY-MM'
                            ) as label
                        )
                        SELECT 
                            m.label,
                            COALESCE(COUNT(e.event_id), 0) as value
                        FROM months m
                        LEFT JOIN event e
                            ON TO_CHAR(e.start_datetime, 'YYYY-MM') = m.label
                        GROUP BY m.label
                        ORDER BY m.label DESC
                    """, (duration,))
                    
            elif data_source == "events_by_severity":
                cursor.execute("""
                    SELECT 
                        COALESCE(r.gravity, 'Non spécifié') as label,
                        COUNT(*) as value
                    FROM event e
                    LEFT JOIN event_risk er ON e.event_id = er.event_id
                    LEFT JOIN risk r ON er.risk_id = r.risk_id
                    GROUP BY r.gravity
                    ORDER BY value DESC
                """)
                
            elif data_source == "events_by_location":
                cursor.execute("""
                    SELECT 
                        COALESCE(ou.location, 'Non spécifié') as label,
                        COUNT(*) as value
                    FROM event e
                    LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
                    GROUP BY ou.location
                    ORDER BY value DESC
                    LIMIT 10
                """)
                
            elif data_source == "measures_by_cost":
                cursor.execute("""
                    SELECT 
                        cm.name as label,
                        cm.cost::numeric as value
                    FROM corrective_measure cm
                    WHERE cm.cost IS NOT NULL AND cm.cost > 0
                    ORDER BY cm.cost DESC
                    LIMIT 15
                """)
            else:
                # Par défaut: événements par catégorie
                cursor.execute("""
                    SELECT 
                        e.type as label,
                        COUNT(*) as value
                    FROM event e
                    WHERE e.type IS NOT NULL
                    GROUP BY e.type
                    ORDER BY value DESC
                    LIMIT 10
                """)
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return {
                "labels": [row['label'] for row in rows],
                "values": [float(row['value']) for row in rows]
            }
            
        except Exception as e:
            print(f"❌ Erreur récupération données: {e}")
            return {"labels": [], "values": []}
    
    def process_query(self, user_query: str) -> Dict:
        """Traite la requête utilisateur et génère la visualisation."""
        
        # Analyser la requête
        analysis = self.analyze_query(user_query)
        
        if not analysis:
            return {
                "type": "text",
                "content": "❌ Je n'ai pas pu comprendre votre demande de visualisation. Pouvez-vous reformuler?"
            }
        
        # Récupérer les données
        data = self.get_data_for_visualization(
            analysis.get('data_source', 'events_by_category'),
            analysis.get('filters', {})
        )
        
        if not data['labels']:
            return {
                "type": "text",
                "content": "❌ Aucune donnée disponible pour cette visualisation."
            }
        
        # Retourner la configuration du graphique
        return {
            "type": "chart",
            "chart_type": analysis.get('chart_type', 'bar'),
            "title": analysis.get('title', 'Visualisation des données'),
            "description": analysis.get('description', ''),
            "data": data
        }

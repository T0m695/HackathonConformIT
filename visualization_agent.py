import os
import json
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from database import get_connection
import psycopg2.extras
from datetime import datetime, timedelta

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
        
        # Date par défaut: 2 ans avant aujourd'hui
        default_start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        default_end_date = datetime.now().strftime('%Y-%m-%d')
        
        system_prompt = f"""Tu es un assistant spécialisé dans l'analyse de données de sécurité industrielle.
Analyse la requête de l'utilisateur et détermine:
1. Le type de graphique approprié (bar, line, pie, doughnut, scatter)
2. Les données à afficher
3. Le titre du graphique
4. Les filtres à appliquer (dates, catégories, etc.)

Si l'utilisateur ne spécifie pas de dates, utilise:
- Date de début par défaut: {default_start_date} (il y a 2 ans)
- Date de fin par défaut: {default_end_date} (aujourd'hui)

Exemples de dates à reconnaître:
- "depuis janvier 2023"
- "entre 2022 et 2023"
- "les 6 derniers mois"
- "depuis le début de l'année"


Peu importe la demande de l'utilisateur, Réponds UNIQUEMENT avec un JSON valide au format suivant:
{{
    "chart_type": "bar|line|pie|doughnut|scatter",
    "data_source": "events_by_category|events_by_month|events_by_severity|events_by_location|measures_by_cost",
    "title": "Titre du graphique",
    "filters": {{
        "start_date": "{default_start_date}",
        "end_date": "{default_end_date}",
        "duration": 12,
        "category": null,
        "severity": null
    }},
    "description": "Description courte"
}}"""
        
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
                parsed_data = json.loads(ai_response[json_start:json_end])
                
                # Assurer les valeurs par défaut
                if 'filters' not in parsed_data:
                    parsed_data['filters'] = {}
                
                if 'start_date' not in parsed_data['filters'] or not parsed_data['filters']['start_date']:
                    parsed_data['filters']['start_date'] = default_start_date
                    
                if 'end_date' not in parsed_data['filters'] or not parsed_data['filters']['end_date']:
                    parsed_data['filters']['end_date'] = default_end_date
                
                return parsed_data
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
            
            # Extraire les dates des filtres
            start_date = filters.get('start_date', (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d'))
            end_date = filters.get('end_date', datetime.now().strftime('%Y-%m-%d'))
            
            print(f"🔍 Filtres appliqués: {start_date} à {end_date}")
            
            if data_source == "events_by_category":
                cursor.execute("""
                    SELECT 
                        e.type as label,
                        COUNT(*) as value
                    FROM event e
                    WHERE e.type IS NOT NULL
                        AND e.start_datetime >= %s::date
                        AND e.start_datetime <= %s::date
                    GROUP BY e.type
                    ORDER BY value DESC
                    LIMIT 10
                """, (start_date, end_date))
                
            elif data_source == "events_by_month":
                cursor.execute("""
                    SELECT 
                        TO_CHAR(e.start_datetime, 'YYYY-MM') as label,
                        COUNT(*) as value
                    FROM event e
                    WHERE e.start_datetime IS NOT NULL
                        AND e.start_datetime >= %s::date
                        AND e.start_datetime <= %s::date
                    GROUP BY TO_CHAR(e.start_datetime, 'YYYY-MM')
                    ORDER BY label ASC
                """, (start_date, end_date))
                    
            elif data_source == "events_by_severity":
                cursor.execute("""
                    SELECT 
                        COALESCE(r.gravity, 'Non spécifié') as label,
                        COUNT(*) as value
                    FROM event e
                    LEFT JOIN event_risk er ON e.event_id = er.event_id
                    LEFT JOIN risk r ON er.risk_id = r.risk_id
                    WHERE e.start_datetime >= %s::date
                        AND e.start_datetime <= %s::date
                    GROUP BY r.gravity
                    ORDER BY value DESC
                """, (start_date, end_date))
                
            elif data_source == "events_by_location":
                cursor.execute("""
                    SELECT 
                        COALESCE(ou.location, 'Non spécifié') as label,
                        COUNT(*) as value
                    FROM event e
                    LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
                    WHERE e.start_datetime >= %s::date
                        AND e.start_datetime <= %s::date
                    GROUP BY ou.location
                    ORDER BY value DESC
                    LIMIT 10
                """, (start_date, end_date))
                
            elif data_source == "measures_by_cost":
                cursor.execute("""
                    SELECT 
                        cm.name as label,
                        cm.cost::numeric as value
                    FROM corrective_measure cm
                    WHERE cm.cost IS NOT NULL AND cm.cost > 0
                        AND cm.implementation_date >= %s::date
                        AND cm.implementation_date <= %s::date
                    ORDER BY cm.cost DESC
                    LIMIT 15
                """, (start_date, end_date))
            else:
                # Par défaut: événements par catégorie avec filtres de dates
                cursor.execute("""
                    SELECT 
                        e.type as label,
                        COUNT(*) as value
                    FROM event e
                    WHERE e.type IS NOT NULL
                        AND e.start_datetime >= %s::date
                        AND e.start_datetime <= %s::date
                    GROUP BY e.type
                    ORDER BY value DESC
                    LIMIT 10
                """, (start_date, end_date))
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            print(f"✅ {len(rows)} lignes de données récupérées")
            
            return {
                "labels": [row['label'] for row in rows],
                "values": [float(row['value']) for row in rows]
            }
            
        except Exception as e:
            print(f"❌ Erreur récupération données: {e}")
            import traceback
            traceback.print_exc()
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
                "content": "❌ Aucune donnée disponible pour cette visualisation dans la période spécifiée."
            }
        
        # Ajouter les informations de période au titre/description
        filters = analysis.get('filters', {})
        start_date = filters.get('start_date', 'N/A')
        end_date = filters.get('end_date', 'N/A')
        
        period_info = f"Période: {start_date} au {end_date}"
        description = analysis.get('description', '')
        if description:
            description = f"{description} - {period_info}"
        else:
            description = period_info
        
        # Retourner la configuration du graphique
        return {
            "type": "chart",
            "chart_type": analysis.get('chart_type', 'bar'),
            "title": analysis.get('title', 'Visualisation des données'),
            "description": description,
            "data": data,
            "filters": filters
        }

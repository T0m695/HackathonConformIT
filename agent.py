"""
Enhanced Event Agent using ATTEMPT1's RAG Pipeline and SQL Generation capabilities.
"""
from typing import Dict, List, Optional, Tuple
import json
from ATTEMPT1.pipeline import EnhancedRAGPipeline
from ATTEMPT1.config import Config, debug_print

class EventAgent:
    """Agent IA avancé pour interroger et analyser les événements de sécurité."""
    
    def __init__(self):
        """Initialise l'agent avec le pipeline RAG amélioré."""
        try:
            # Initialize the enhanced RAG pipeline
            self.pipeline = EnhancedRAGPipeline()
            debug_print("✅ Pipeline RAG avancé initialisé avec succès")
            
            # Configure performance profile
            Config.EMBEDDING_BATCH_SIZE = 32  # Optimisé pour les requêtes en temps réel
            Config.EMBEDDING_MAX_WORKERS = 4  # Utilise le multithreading pour de meilleures performances
            debug_print(f"⚡ Optimisations batch activées (batch_size={Config.EMBEDDING_BATCH_SIZE}, workers={Config.EMBEDDING_MAX_WORKERS})")
            
        except Exception as e:
            raise ValueError(f"❌ Erreur lors de l'initialisation du pipeline RAG: {str(e)}")
            
    def process_query(self, question: str) -> Tuple[str, Dict]:
        """
        Traite une question en langage naturel et retourne une réponse structurée.
        
        Args:
            question: La question en langage naturel
            
        Returns:
            Tuple[str, Dict]: (réponse formatée, métadonnées supplémentaires)
        """
        try:
            # Process the query through the RAG pipeline
            answer = self.pipeline.ask(question)
            
            # Format the response
            response = {
                "answer": answer.get("answer", ""),
                "sql": answer.get("sql", ""),
                "context": answer.get("context", []),
                "confidence": answer.get("confidence", 0.0)
            }
            
            # Extract metadata
            metadata = {
                "sql_query": answer.get("sql", ""),
                "context_used": bool(answer.get("context")),
                "confidence_score": answer.get("confidence", 0.0),
                "processing_time": answer.get("processing_time", 0.0)
            }
            
            # Format human readable response
            human_response = response["answer"]
            if not human_response:
                human_response = "Je n'ai pas trouvé de réponse précise à votre question. Pourriez-vous la reformuler?"
                
            return human_response, metadata
            
        except Exception as e:
            debug_print(f"❌ Erreur lors du traitement de la requête: {str(e)}")
            raise ValueError(f"Erreur lors du traitement de la requête: {str(e)}")
            
    def search_events(self, query: str) -> Dict:
        """
        Point d'entrée principal pour la recherche d'événements.
        Compatible avec l'interface existante de l'application.
        
        Args:
            query: La requête en langage naturel
            
        Returns:
            Dict: La réponse formatée avec les métadonnées
        """
        try:
            response, metadata = self.process_query(query)
            return {
                "response": response,
                "metadata": metadata
            }
        except Exception as e:
            debug_print(f"❌ Erreur lors de la recherche: {str(e)}")
            return {
                "response": f"Une erreur s'est produite: {str(e)}",
                "metadata": {"error": str(e)}
            }
        self.events = load_events()
        print(f"🔍 DEBUG: Événements chargés: {len(self.events)}")
        
        if self.events:
            print(f"🔍 DEBUG: Premier événement: {self.events[0]}")
        else:
            print("⚠️ DEBUG: Aucun événement chargé!")
            
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    def _format_response(self, response: Dict) -> Dict:
        """Format la réponse du pipeline pour l'interface web."""
        if not response:
            return {
                "response": "❌ Le pipeline RAG n'a pas retourné de réponse",
                "metadata": {"error": "no_response"}
            }
            
        # Format the response
        answer = response.get("answer", "")
        if not answer:
            answer = "Je n'ai pas trouvé de réponse précise à cette question. Pourriez-vous la reformuler?"
            
        # Add emojis based on response type
        if "error" in response:
            answer = f"❌ {answer}"
        elif response.get("confidence", 0) > 0.8:
            answer = f"✅ {answer}"
        else:
            answer = f"ℹ️ {answer}"
            
        try:
            return {
                "response": answer,
                "metadata": {
                    "sql_query": response.get("sql", ""),
                    "context": response.get("context", []),
                    "confidence": response.get("confidence", 0.0),
                    "processing_time": response.get("processing_time", 0.0),
                    "search_strategy": response.get("search_strategy", "semantic")
                }
            }
        except Exception as e:
            raise ValueError(f"❌ Erreur de formatage de la réponse: {e}")
            
    def _extract_insights(self, results: Dict) -> Dict:
        """Extrait les insights clés des résultats."""
        insights = {
            "key_findings": [],
            "metrics": {},
            "recommendations": []
        }
        
        try:
            if "context" in results:
                # Analyze events in context
                event_count = len(results["context"])
                severity_levels = {}
                for event in results["context"]:
                    severity = event.get("severity", "unknown")
                    severity_levels[severity] = severity_levels.get(severity, 0) + 1
                
                insights["metrics"] = {
                    "total_events": event_count,
                    "severity_distribution": severity_levels
                }
                
            if "recommendations" in results:
                insights["recommendations"] = results["recommendations"]
                
        except Exception as e:
            debug_print(f"⚠️ Erreur lors de l'extraction des insights: {e}")
            
        return insights
    
    def get_all_categories(self) -> List[str]:
        """Retourne toutes les catégories d'événements."""
        categories = set()
        for event in self.events:
            if 'categorie' in event:
                categories.add(event['categorie'])
        return sorted(list(categories))

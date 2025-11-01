# main.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced RAG Text-to-SQL for EHS PostgreSQL DB v2 - FAISS Edition
"""

from config import Config, logger
from pipeline import EnhancedRAGPipeline

def main():
    """Interactive CLI"""
    logger.info("Initializing Enhanced RAG Pipeline with FAISS...")
    
    try:
        pipeline = EnhancedRAGPipeline()
        logger.info("Pipeline ready!")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        return
    
    print("\n" + "="*80)
    print(" 🚀 Enhanced Text-to-SQL RAG System v2 - FAISS TURBO Edition")
    print("="*80)
    print(" Commands:")
    print("   • 'exit' ou 'quit' - Quitter l'application")
    print("   • 'clear' - Effacer l'historique et le cache")
    print("   • 'rebuild' - Reconstruire l'index FAISS du schéma")
    print("   • 'build_faiss_indexes' - Construire les index FAISS pour les champs TEXT")
    print("   • 'profile:fast|balanced|safe' - Changer le profil de performance")
    print("   • 'faiss_stats' - Afficher les statistiques des index FAISS")
    print("   • 'search:table.column:query' - Recherche vectorielle directe")
    print("     Exemple: search:event.description:chute de hauteur")
    print("   • 'stats' - Afficher les statistiques générales")
    print("="*80 + "\n")
    print(" ⚡ OPTIMISATIONS BATCH ACTIVÉES!")
    print(f"    • Batch size: {Config.EMBEDDING_BATCH_SIZE}")
    print(f"    • Workers parallèles: {Config.EMBEDDING_MAX_WORKERS}")
    print(f"    • Profil actuel: BALANCED (utilisez 'profile:fast' pour plus de vitesse)\n")
    
    query_count = {"success": 0, "failed": 0, "cached": 0, "faiss_search": 0}
    
    while True:
        try:
            question = input("\n🔎 Question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['exit', 'quit']:
                print("\n👋 Au revoir!")
                break
            
            if question.lower() == 'clear':
                pipeline.clear_cache_and_history()
                query_count = {"success": 0, "failed": 0, "cached": 0, "faiss_search": 0}
                print("✅ Historique et cache effacés")
                continue
            
            if question.lower() == 'rebuild':
                pipeline.rebuild_index()
                print("✅ Index FAISS du schéma reconstruit")
                continue
            
            if question.lower() == 'build_faiss_indexes':
                pipeline.build_faiss_indexes()
                continue
            
            # Changer le profil de performance
            if question.lower().startswith('profile:'):
                profile = question.split(':', 1)[1].strip().lower()
                try:
                    Config.set_performance_profile(profile)
                except ValueError as e:
                    print(f"❌ {e}")
                continue
            
            if question.lower() == 'faiss_stats':
                pipeline.get_faiss_stats()
                continue
            
            # Recherche vectorielle directe : search:table.column:query
            if question.startswith('search:'):
                try:
                    parts = question[7:].split(':', 2)
                    if len(parts) != 3:
                        print("❌ Format invalide. Utilisez: search:table.column:votre question")
                        continue
                    
                    table, column, search_query = parts
                    result = pipeline.search_in_text(search_query, table, column, top_k=5)
                    
                    if result["success"]:
                        query_count["faiss_search"] += 1
                        
                        print("\n" + "="*80)
                        print(f"🔍 RÉSULTATS DE RECHERCHE VECTORIELLE FAISS")
                        print(f"   Table: {result['table']}")
                        print(f"   Colonne: {result['column']}")
                        print(f"   Temps: {result['execution_time']:.2f}s")
                        print("="*80)
                        
                        for res in result["results"]:
                            print(f"\n🔸 Rang #{res['rank']} (Similarité: {res['similarity']:.4f}, Distance: {res['distance']:.4f})")
                            print("─"*80)
                            text_preview = res['text'][:300] + "..." if len(res['text']) > 300 else res['text']
                            print(text_preview)
                        
                        print("\n" + "="*80)
                        print("\nℹ️  Similarité: Plus la valeur est ÉLEVÉE, plus le texte est similaire")
                        print("    Distance: Plus la valeur est PETITE, plus le texte est similaire")
                    else:
                        print(f"\n❌ Erreur: {result['error']}")
                    
                    continue
                    
                except Exception as e:
                    print(f"❌ Erreur lors de la recherche: {e}")
                    continue
            
            if question.lower() == 'stats':
                print(f"\n📊 Statistiques:")
                print(f"   • Requêtes SQL réussies: {query_count['success']}")
                print(f"   • Requêtes échouées: {query_count['failed']}")
                print(f"   • Requêtes du cache: {query_count['cached']}")
                print(f"   • Recherches FAISS directes: {query_count['faiss_search']}")
                continue
            
            # Requête SQL normale
            print("\n⏳ Traitement...")
            response = pipeline.ask(question)
            
            if response["success"]:
                if response["from_cache"]:
                    query_count["cached"] += 1
                else:
                    query_count["success"] += 1
                
                # Afficher si la recherche vectorielle TEXT a été utilisée
                if response.get("used_text_search"):
                    print("\n✨ Recherche vectorielle TEXT utilisée pour enrichir le contexte!")
                
                print(f"\n✅ SQL généré ({response['execution_time']:.2f}s):")
                print("─" * 80)
                print(response["sql"])
                print("─" * 80)
                
                print(f"\n📊 Résultat:")
                result_preview = str(response["result"])
                if len(result_preview) > 1000:
                    print(result_preview[:1000] + "\n... (tronqué)")
                else:
                    print(result_preview)
                
                if response["from_cache"]:
                    print("\n💾 (Résultat du cache)")
            else:
                query_count["failed"] += 1
                print(f"\n❌ Erreur: {response['error']}")
        
        except KeyboardInterrupt:
            print("\n\n👋 Interruption détectée. Au revoir!")
            break
        except Exception as e:
            query_count["failed"] += 1
            logger.error(f"Unexpected error: {e}", exc_info=True)
            print(f"\n❌ Erreur inattendue: {e}")

if __name__ == "__main__":
    main()
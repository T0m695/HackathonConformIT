"""
Exemple d'utilisation de query_with_ai() avec PostgreSQL
"""
import psycopg2
import psycopg2.extras
from ai_query import query_with_ai


def get_sql_results(query: str) -> list:
    """
    Exécute une requête SQL sur PostgreSQL et retourne les résultats.
    
    Args:
        query: Requête SQL à exécuter
        
    Returns:
        Liste de dictionnaires contenant les résultats
    """
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="hackathon",
            user="postgres",
            password="admin",
            port=5432
        )
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Convertir RealDictRow en dict simple
        results = [dict(row) for row in results]
        
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f"❌ Erreur SQL: {e}")
        return []


# Exemples d'utilisation
if __name__ == "__main__":
    print("=" * 80)
    print("EXEMPLES D'UTILISATION AVEC POSTGRESQL")
    print("=" * 80)
    
    # Exemple 1: Analyser les mesures correctives
    print("\n📌 EXEMPLE 1: Analyse des mesures correctives\n")
    print("-" * 80)
    
    sql_query_1 = """
        SELECT 
            measure_id,
            name,
            description,
            implementation_date,
            organizational_unit_id
        FROM corrective_measure
        LIMIT 10
    """
    
    results_1 = get_sql_results(sql_query_1)
    prompt_1 = "Quelles sont les mesures correctives les plus récentes et que recommandes-tu?"
    
    if results_1:
        print(f"📊 {len(results_1)} résultats trouvés\n")
        reponse_1 = query_with_ai(results_1, prompt_1)
        print(reponse_1)
    
    # Exemple 2: Statistiques par unité organisationnelle
    print("\n\n📌 EXEMPLE 2: Statistiques par unité\n")
    print("-" * 80)
    
    sql_query_2 = """
        SELECT 
            organizational_unit_id,
            COUNT(*) as total_mesures
        FROM corrective_measure
        GROUP BY organizational_unit_id
        ORDER BY total_mesures DESC
        LIMIT 5
    """
    
    results_2 = get_sql_results(sql_query_2)
    prompt_2 = "Quelle unité a le plus de mesures correctives? Est-ce préoccupant?"
    
    if results_2:
        print(f"📊 {len(results_2)} résultats trouvés\n")
        reponse_2 = query_with_ai(results_2, prompt_2)
        print(reponse_2)
    
    # Exemple 3: Analyse temporelle
    print("\n\n📌 EXEMPLE 3: Analyse temporelle\n")
    print("-" * 80)
    
    sql_query_3 = """
        SELECT 
            TO_CHAR(implementation_date, 'YYYY-MM') as mois,
            COUNT(*) as nombre_mesures
        FROM corrective_measure
        WHERE implementation_date IS NOT NULL
        GROUP BY TO_CHAR(implementation_date, 'YYYY-MM')
        ORDER BY mois DESC
        LIMIT 12
    """
    
    results_3 = get_sql_results(sql_query_3)
    prompt_3 = "Analyse l'évolution du nombre de mesures correctives. Y a-t-il une tendance?"
    
    if results_3:
        print(f"📊 {len(results_3)} résultats trouvés\n")
        reponse_3 = query_with_ai(results_3, prompt_3)
        print(reponse_3)
    
    print("\n\n" + "=" * 80)
    print("✅ Tous les exemples terminés!")
    print("=" * 80)

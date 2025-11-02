import psycopg2
import psycopg2.extras
from typing import List, Dict, Tuple
from datetime import datetime
from collections import defaultdict
import hashlib
from database import get_connection

class DuplicateDetector:
    """Détecte les doublons exacts dans les événements de sécurité."""
    
    def __init__(self):
        pass
    
    def detect_duplicates(self, 
                         date_range_days: int = None) -> Dict:
        """
        Détecte les groupes de doublons exacts dans la base de données.
        Utilise une approche par hashing pour des performances optimales.
        
        Args:
            date_range_days: Nombre de jours à analyser (None = tous)
        
        Returns:
            Dict contenant les statistiques et les groupes de doublons
        """
        print(f"🔍 Détection des doublons exacts")
        
        # Charger les événements avec une requête optimisée
        groups = self._find_exact_duplicates_sql(date_range_days)

        # Calculer les statistiques
        stats = self._calculate_stats(groups)
        
        return {
            "stats": stats,
            "groups": groups,
            "timestamp": datetime.now().isoformat()
        }
    def _find_exact_duplicates_sql(self, date_range_days: int = None) -> List[List[int]]:
        """Recherche les doublons exacts dans la base de données."""
        query = """
            SELECT event_data, ARRAY_AGG(id) AS event_ids, COUNT(*) AS count
            FROM event
        """
        params = []
        if date_range_days is not None:
            query += " WHERE event_timestamp >= NOW() - INTERVAL %s DAY"
            params.append(date_range_days)
        query += """
            GROUP BY event_data
            HAVING COUNT(*) > 1
        """
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
        
        groups = [list(row['event_ids']) for row in rows]
        return groups
    
    def _find_exact_duplicates_sql(self, date_range_days: int = None) -> List[Dict]:
        """
        Trouve les doublons exacts directement en SQL pour des performances maximales.
        Compare: classification, description, type, location
        """
        try:
            conn = get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Construire le filtre de date
            date_filter = ""
            params = []
            if date_range_days:
                date_filter = "AND e.start_datetime >= CURRENT_DATE - INTERVAL '%s days'"
                params.append(date_range_days)
            
            # Requête SQL optimisée avec GROUP BY pour trouver les doublons
            query = f"""
                WITH duplicate_groups AS (
                    SELECT 
                        COALESCE(e.classification, '') as classification,
                        COALESCE(e.description, '') as description,
                        COALESCE(e.type, '') as type,
                        COALESCE(ou.location, '') as location,
                        COUNT(*) as dup_count,
                        ARRAY_AGG(e.event_id ORDER BY e.start_datetime DESC) as event_ids
                    FROM event e
                    LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
                    WHERE 1=1 {date_filter}
                    GROUP BY 
                        COALESCE(e.classification, ''),
                        COALESCE(e.description, ''),
                        COALESCE(e.type, ''),
                        COALESCE(ou.location, '')
                    HAVING COUNT(*) > 1
                )
                SELECT 
                    dg.event_ids,
                    dg.classification,
                    dg.description,
                    dg.type,
                    dg.location,
                    dg.dup_count
                FROM duplicate_groups dg
                ORDER BY dg.dup_count DESC
            """
            
            cursor.execute(query, params)
            duplicate_groups = cursor.fetchall()
            
            # Pour chaque groupe de doublons, charger les détails des événements
            groups = []
            for idx, dup_group in enumerate(duplicate_groups, 1):
                event_ids = dup_group['event_ids']
                
                # Charger les détails de chaque événement du groupe
                cursor.execute("""
                    SELECT 
                        e.event_id as id,
                        COALESCE(e.classification, 'Sans titre') as titre,
                        COALESCE(e.description, '') as description,
                        TO_CHAR(e.start_datetime, 'YYYY-MM-DD') as date,
                        e.type as categorie,
                        COALESCE(ou.location, 'Non spécifié') as lieu,
                        (
                            SELECT COUNT(*)
                            FROM event_corrective_measure ecm
                            WHERE ecm.event_id = e.event_id
                        ) as nb_mesures
                    FROM event e
                    LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
                    WHERE e.event_id = ANY(%s)
                    ORDER BY e.start_datetime DESC
                """, (event_ids,))
                
                events = [dict(row) for row in cursor.fetchall()]
                
                groups.append({
                    "group_id": idx,
                    "similarity": 1.0,  # 100% pour des doublons exacts
                    "status": "pending",
                    "events": events,
                    "dup_count": len(events)
                })
            
            cursor.close()
            conn.close()
            
            return groups
            
        except Exception as e:
            print(f"❌ Erreur détection doublons: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _calculate_stats(self, groups: List[Dict]) -> Dict:
        """Calcule les statistiques des doublons."""
        total_groups = len(groups)
        total_duplicates = sum(len(g['events']) for g in groups)
        to_review = sum(1 for g in groups if g.get('status') == 'pending')
        
        return {
            "total_groups": total_groups,
            "total_duplicates": total_duplicates,
            "to_review": to_review
        }
    
    def merge_events(self, event_ids: List[int], keep_id: int) -> bool:
        """
        Fusionne plusieurs événements en un seul.
        
        Args:
            event_ids: Liste des IDs d'événements à fusionner
            keep_id: ID de l'événement à conserver
        
        Returns:
            True si la fusion a réussi
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Vérifier que keep_id est dans la liste
            if keep_id not in event_ids:
                print(f"❌ L'ID {keep_id} n'est pas dans la liste des événements à fusionner")
                return False
            
            # IDs à supprimer (tous sauf keep_id)
            delete_ids = [id for id in event_ids if id != keep_id]
            
            if not delete_ids:
                print(f"⚠️ Aucun événement à supprimer")
                return True
            
            # Début de la transaction
            cursor.execute("BEGIN")
            
            # Transférer les mesures correctives vers l'événement conservé
            # Éviter les doublons de mesures
            cursor.execute("""
                INSERT INTO event_corrective_measure (event_id, measure_id)
                SELECT %s, ecm.measure_id
                FROM event_corrective_measure ecm
                WHERE ecm.event_id = ANY(%s)
                ON CONFLICT (event_id, measure_id) DO NOTHING
            """, (keep_id, delete_ids))
            
            # Supprimer les associations des événements à supprimer
            cursor.execute("""
                DELETE FROM event_corrective_measure
                WHERE event_id = ANY(%s)
            """, (delete_ids,))
            
            # Transférer les associations de risques
            cursor.execute("""
                INSERT INTO event_risk (event_id, risk_id)
                SELECT %s, er.risk_id
                FROM event_risk er
                WHERE er.event_id = ANY(%s)
                ON CONFLICT (event_id, risk_id) DO NOTHING
            """, (keep_id, delete_ids))
            
            cursor.execute("""
                DELETE FROM event_risk
                WHERE event_id = ANY(%s)
            """, (delete_ids,))
            
            # Supprimer les événements fusionnés
            cursor.execute("""
                DELETE FROM event
                WHERE event_id = ANY(%s)
            """, (delete_ids,))
            
            deleted_count = cursor.rowcount
            
            # Commit de la transaction
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"✅ Fusion réussie: {deleted_count} événement(s) fusionné(s) dans {keep_id}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de la fusion: {e}")
            import traceback
            traceback.print_exc()
            if conn:
                conn.rollback()
                conn.close()
            return False
    
    def dismiss_group(self, event_ids: List[int]) -> bool:
        """
        Marque un groupe de doublons comme ignoré.
        
        Note: Pour l'instant, on se contente de logger.
        Dans une vraie application, on pourrait créer une table
        pour stocker les groupes ignorés.
        """
        print(f"ℹ️ Groupe ignoré: {event_ids}")
        return True
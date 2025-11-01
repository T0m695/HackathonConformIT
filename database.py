import psycopg2
import psycopg2.extras
import os
from typing import List, Dict

def get_connection():
    """Crée une connexion à la base de données PostgreSQL."""
    try:
        print("🔍 DEBUG: Tentative de connexion à PostgreSQL...")
        print(f"🔍 DEBUG: Host=localhost, Database=hackathon, User=postgres, Port=5432")
        
        conn = psycopg2.connect(
            host="localhost",
            database="hackathon",
            user="postgres",
            password="admin",
            port=5432,
            connect_timeout=10,
            options="-c search_path=public"
        )
        
        # Set schema explicitly
        cursor = conn.cursor()
        cursor.execute("SET search_path TO public;")
        conn.commit()
        cursor.close()
        
        print("✅ Connexion PostgreSQL établie avec succès")
        
        # Test immédiat de la connexion
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Version PostgreSQL: {version[0][:50]}...")
        
        # Vérifier le search_path
        cursor.execute("SHOW search_path;")
        search_path = cursor.fetchone()
        print(f"✅ Search path: {search_path[0]}")
        
        cursor.close()
        
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Erreur de connexion PostgreSQL (OperationalError): {e}")
        print("💡 Vérifiez que:")
        print("   - PostgreSQL est démarré")
        print("   - Le port 5432 est accessible")
        print("   - La base de données 'hackathon' existe")
        print("   - L'utilisateur 'postgres' a accès à la base 'hackathon'")
        raise
    except Exception as e:
        print(f"❌ Erreur de connexion PostgreSQL: {e}")
        raise

def init_database():
    """Vérifie que la base de données PostgreSQL est accessible."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("🔍 DEBUG: Vérification de la base de données PostgreSQL...")
        
        # Vérifier toutes les bases de données disponibles
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = cursor.fetchall()
        print(f"🔍 DEBUG: Bases de données disponibles: {[db[0] for db in databases]}")
        
        # Vérifier tous les schémas disponibles
        cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema';")
        schemas = cursor.fetchall()
        print(f"🔍 DEBUG: Schémas disponibles: {[s[0] for s in schemas]}")
        
        # Vérifier les tables dans tous les schémas
        cursor.execute("""
            SELECT schemaname, tablename 
            FROM pg_tables 
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename;
        """)
        all_tables = cursor.fetchall()
        print(f"🔍 DEBUG: Toutes les tables trouvées:")
        for schema, table in all_tables:
            print(f"   - {schema}.{table}")
        
        # Vérifier spécifiquement corrective_measure
        cursor.execute("""
            SELECT schemaname, tablename, tableowner
            FROM pg_tables 
            WHERE tablename = 'corrective_measure';
        """)
        cm_tables = cursor.fetchall()
        if cm_tables:
            print(f"🔍 DEBUG: Table corrective_measure trouvée dans:")
            for schema, table, owner in cm_tables:
                print(f"   - Schéma: {schema}, Propriétaire: {owner}")
                
                # Compter les enregistrements
                cursor.execute(f"SELECT COUNT(*) FROM {schema}.corrective_measure")
                count = cursor.fetchone()[0]
                print(f"     Nombre d'enregistrements: {count}")
                
                # Lister les colonnes
                cursor.execute(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = '{schema}' 
                    AND table_name = 'corrective_measure'
                    ORDER BY ordinal_position;
                """)
                columns = cursor.fetchall()
                print(f"     Colonnes: {[(col[0], col[1]) for col in columns]}")
        else:
            print("❌ Table corrective_measure NON TROUVÉE dans aucun schéma!")
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✓ Diagnostic de la base de données terminé")
        
    except psycopg2.Error as e:
        print(f"❌ Erreur PostgreSQL: {e.pgerror if hasattr(e, 'pgerror') else str(e)}")
        print(f"Code d'erreur: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"✗ Erreur lors de la vérification: {e}")
        import traceback
        traceback.print_exc()

def load_events() -> List[Dict]:
    """Charge tous les événements depuis PostgreSQL."""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("🔍 DEBUG: Chargement des événements depuis PostgreSQL...")
        
        query = """
            SELECT 
                cm.measure_id as id,
                cm.name as titre,
                cm.description,
                TO_CHAR(cm.implementation_date, 'YYYY-MM-DD') as date,
                cm.cost::text as cout,
                cm.organizational_unit_id as unite_id,
                COALESCE(ou.location, 'Non spécifié') as lieu,
                'Mesure corrective' as categorie
            FROM corrective_measure cm
            LEFT JOIN organizational_unit ou ON cm.organizational_unit_id = ou.unit_id
            ORDER BY cm.measure_id DESC 
            LIMIT 100
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"✅ {len(rows)} événements chargés")
        
        events = []
        for row in rows:
            event = dict(row)
            
            if not event.get('titre'):
                event['titre'] = f"Mesure corrective #{event.get('id', 'N/A')}"
            if not event.get('description'):
                event['description'] = 'Description non disponible'
            if not event.get('date'):
                event['date'] = '2024-01-01'
            
            event['categorie'] = 'Mesure corrective'
                
            events.append(event)
        
        cursor.close()
        conn.close()
            
        return events
        
    except Exception as e:
        print(f"❌ Erreur lors du chargement: {e}")
        return []

def format_event(event: Dict) -> str:
    """Formate un événement pour l'affichage."""
    return f"""
Titre: {event.get('titre', 'N/A')}
Date: {event.get('date', 'N/A')}
Lieu: {event.get('lieu', 'N/A')}
Description: {event.get('description', 'N/A')}
Catégorie: {event.get('categorie', 'N/A')}
"""

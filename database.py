import psycopg2
import psycopg2.extras
import os
from typing import List, Dict

def get_connection():
    """Crée une connexion à la base de données PostgreSQL."""
    try:
        # Utiliser host.docker.internal si on est dans Docker, sinon localhost
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "hackathon")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "admin")
        
        print(f"🔍 DEBUG: Tentative de connexion à PostgreSQL...")
        print(f"🔍 DEBUG: Host={db_host}, Database={db_name}, User={db_user}, Port={db_port}")
        
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            port=db_port,
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
        print(f"   - PostgreSQL est démarré")
        print(f"   - Le port {db_port} est accessible")
        print(f"   - La base de données '{db_name}' existe")
        print(f"   - L'utilisateur '{db_user}' a accès à la base '{db_name}'")
        print("   - Si vous êtes dans Docker, utilisez DB_HOST=host.docker.internal")
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
                e.event_id as id,
                e.classification as titre,
                e.description,
                TO_CHAR(e.start_datetime, 'YYYY-MM-DD') as date,
                e.type as categorie,
                COALESCE(ou.location, 'Non spécifié') as lieu,
                -- Charger les mesures correctives associées
                (
                    SELECT json_agg(
                        json_build_object(
                            'measure_id', cm.measure_id,
                            'name', cm.name,
                            'description', cm.description,
                            'implementation_date', TO_CHAR(cm.implementation_date, 'YYYY-MM-DD'),
                            'cost', cm.cost::text
                        )
                    )
                    FROM event_corrective_measure ecm
                    JOIN corrective_measure cm ON ecm.measure_id = cm.measure_id
                    WHERE ecm.event_id = e.event_id
                ) as mesures_correctives
            FROM event e
            LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
            ORDER BY e.start_datetime DESC 
            LIMIT 100
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"✅ {len(rows)} événements chargés")
        
        events = []
        for row in rows:
            event = dict(row)
            
            if not event.get('titre'):
                event['titre'] = f"Événement #{event.get('id', 'N/A')}"
            if not event.get('description'):
                event['description'] = 'Description non disponible'
            if not event.get('date'):
                event['date'] = '2024-01-01'
            
            # Convertir les mesures correctives de JSON à liste Python
            if event.get('mesures_correctives'):
                event['mesures_correctives'] = event['mesures_correctives']
            else:
                event['mesures_correctives'] = []
                
            events.append(event)
        
        cursor.close()
        conn.close()
            
        return events
        
    except Exception as e:
        print(f"❌ Erreur lors du chargement: {e}")
        return []

def format_event(event: Dict) -> str:
    """Formate un événement pour l'affichage."""
    formatted = f"""
Titre: {event.get('titre', 'N/A')}
Date: {event.get('date', 'N/A')}
Lieu: {event.get('lieu', 'N/A')}
Description: {event.get('description', 'N/A')}
Catégorie: {event.get('categorie', 'N/A')}
"""
    
    # Ajouter les mesures correctives si elles existent
    mesures = event.get('mesures_correctives', [])
    if mesures:
        formatted += "\nMesures correctives associées:\n"
        for i, mesure in enumerate(mesures, 1):
            formatted += f"  {i}. {mesure.get('name', 'N/A')}\n"
            if mesure.get('description'):
                formatted += f"     {mesure.get('description')[:100]}...\n"
            formatted += f"     Date: {mesure.get('implementation_date', 'N/A')}, Coût: {mesure.get('cost', 'N/A')}$\n"
    
    return formatted

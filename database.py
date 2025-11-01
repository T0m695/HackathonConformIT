import sqlite3
import os
import re
from typing import List, Dict

def get_connection():
    """Crée une connexion à la base de données SQLite."""
    # Créer le chemin complet vers la base de données dans le répertoire du projet
    db_path = os.path.join(os.path.dirname(__file__), 'events.db')
    print(f"🔍 DEBUG: Chemin de la base de données: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def parse_postgresql_data():
    """Parse les données du fichier PostgreSQL et les convertit pour SQLite."""
    try:
        sql_file_path = os.path.join(os.path.dirname(__file__), 'data', 'events.sql')
        print(f"🔍 DEBUG: Lecture du fichier PostgreSQL: {sql_file_path}")
        
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extraire les données de la table corrective_measure
        # Chercher les lignes COPY qui contiennent les données
        copy_pattern = r'COPY public\.corrective_measure.*?FROM stdin;(.*?)\\\\.'
        match = re.search(copy_pattern, content, re.DOTALL)
        
        events = []
        if match:
            data_lines = match.group(1).strip().split('\n')
            print(f"🔍 DEBUG: Trouvé {len(data_lines)} lignes de données")
            
            for line in data_lines:
                if line.strip() and not line.startswith('--'):
                    # Parse chaque ligne de données (format tab-separated)
                    parts = line.split('\t')
                    if len(parts) >= 6:
                        events.append({
                            'titre': parts[1] if len(parts) > 1 else 'Événement',
                            'date': parts[4] if len(parts) > 4 and parts[4] != '\\N' else '2024-01-01',
                            'lieu': f"Unité {parts[6]}" if len(parts) > 6 else 'Non spécifié',
                            'description': parts[2] if len(parts) > 2 else 'Description non disponible',
                            'categorie': 'Mesure corrective'
                        })
        
        print(f"🔍 DEBUG: {len(events)} événements extraits du fichier PostgreSQL")
        return events
        
    except Exception as e:
        print(f"❌ DEBUG: Erreur lors du parsing PostgreSQL: {e}")
        return []

def init_database():
    """Initialise la base de données à partir du fichier SQL."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        print(f"🔍 DEBUG: Initialisation de la base de données")
        
        # Créer la table events compatible SQLite
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titre TEXT NOT NULL,
                date TEXT,
                lieu TEXT,
                description TEXT,
                categorie TEXT
            )
        ''')
        
        # Vérifier si la table est vide
        cursor.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        print(f"🔍 DEBUG: Nombre d'événements existants: {count}")
        
        if count == 0:
            print("🔍 DEBUG: Chargement des données depuis le fichier PostgreSQL...")
            # Charger les vraies données depuis le fichier SQL
            real_events = parse_postgresql_data()
            
            if real_events:
                for event in real_events:
                    cursor.execute(
                        "INSERT INTO events (titre, date, lieu, description, categorie) VALUES (?, ?, ?, ?, ?)",
                        (event['titre'], event['date'], event['lieu'], event['description'], event['categorie'])
                    )
                print(f"🔍 DEBUG: {len(real_events)} événements réels insérés")
            else:
                print("⚠️ DEBUG: Aucune donnée trouvée, utilisation de données de test minimales")
                # Insérer seulement quelques données de test si le parsing échoue
                test_events = [
                    ("Conférence Sécurité", "2024-03-15", "Salle principale", "Formation sur les mesures de sécurité", "Formation"),
                    ("Audit Qualité", "2024-04-20", "Bureau qualité", "Audit des processus qualité", "Audit"),
                ]
                cursor.executemany(
                    "INSERT INTO events (titre, date, lieu, description, categorie) VALUES (?, ?, ?, ?, ?)",
                    test_events
                )
        
        conn.commit()
        print("✓ Base de données initialisée avec succès")
        
        # Test de vérification des tables créées
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"🔍 DEBUG: Tables créées: {[table[0] for table in tables]}")
        
        # Vérifier le contenu final
        cursor.execute("SELECT COUNT(*) FROM events")
        final_count = cursor.fetchone()[0]
        print(f"🔍 DEBUG: Nombre total d'événements: {final_count}")
        
    except Exception as e:
        print(f"✗ Erreur lors de l'initialisation: {e}")
    finally:
        conn.close()

def load_events() -> List[Dict]:
    """Charge tous les événements depuis la base de données."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        print("🔍 DEBUG: Tentative de chargement des événements...")
        
        # Vérifier si la table existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events';")
        table_exists = cursor.fetchone()
        print(f"🔍 DEBUG: Table 'events' existe: {table_exists is not None}")
        
        if not table_exists:
            print("⚠️ DEBUG: Table 'events' n'existe pas, initialisation requise")
            return []
        
        cursor.execute("SELECT * FROM events")
        rows = cursor.fetchall()
        print(f"🔍 DEBUG: Nombre d'événements trouvés: {len(rows)}")
        
        events = []
        for row in rows:
            event = {
                'id': row['id'],
                'titre': row['titre'],
                'date': row['date'],
                'lieu': row['lieu'],
                'description': row['description'],
                'categorie': row['categorie']
            }
            events.append(event)
            
        if events:
            print(f"🔍 DEBUG: Premier événement chargé: {events[0]['titre']}")
            
        return events
    except Exception as e:
        print(f"❌ DEBUG: Erreur lors du chargement des événements: {e}")
        return []
    finally:
        conn.close()

def format_event(event: Dict) -> str:
    """Formate un événement pour l'affichage."""
    return f"""
Titre: {event.get('titre', 'N/A')}
Date: {event.get('date', 'N/A')}
Lieu: {event.get('lieu', 'N/A')}
Description: {event.get('description', 'N/A')}
Catégorie: {event.get('categorie', 'N/A')}
"""

"""
Script pour exporter les données du fichier events.sql vers des fichiers CSV
pour utilisation dans AWS RAG.
"""
import sqlite3
import csv as csv_module
import logging
import os
import sys
import re

# Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
OUTPUT_DIR = "csv_exports"
DB_PATH = "events_complete.db"

def extract_copy_data(content, table_name):
    """Extrait les données d'une section COPY du fichier SQL."""
    pattern = rf'COPY public\.{table_name}.*?FROM stdin;(.*?)\\\.'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        lines = []
        for line in match.group(1).strip().split('\n'):
            if line.strip() and not line.startswith('--'):
                # Remplacer \N par None pour NULL
                parts = [None if p == '\\N' else p for p in line.split('\t')]
                lines.append(parts)
        return lines
    return []

def create_full_database():
    """Crée une base SQLite complète depuis le fichier events.sql."""
    sql_file = os.path.join('data', 'events.sql')
    
    if not os.path.exists(sql_file):
        logging.error(f"Fichier {sql_file} non trouvé!")
        return False
    
    logging.info(f"Lecture de {sql_file}...")
    
    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Supprimer l'ancienne base
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        logging.info("Création de la structure de la base de données...")
        
        # Créer les tables
        cursor.execute("""
            CREATE TABLE person (
                person_id INTEGER PRIMARY KEY,
                matricule TEXT NOT NULL,
                name TEXT NOT NULL,
                family_name TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE organizational_unit (
                unit_id INTEGER PRIMARY KEY,
                identifier TEXT NOT NULL,
                name TEXT NOT NULL,
                location TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE risk (
                risk_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                gravity TEXT NOT NULL,
                probability TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE corrective_measure (
                measure_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                owner_id INTEGER NOT NULL,
                implementation_date TEXT,
                cost REAL,
                organizational_unit_id INTEGER NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE event (
                event_id INTEGER PRIMARY KEY,
                declared_by_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                start_datetime TEXT NOT NULL,
                end_datetime TEXT,
                organizational_unit_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                classification TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE event_risk (
                event_id INTEGER NOT NULL,
                risk_id INTEGER NOT NULL,
                PRIMARY KEY (event_id, risk_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE event_corrective_measure (
                event_id INTEGER NOT NULL,
                measure_id INTEGER NOT NULL,
                PRIMARY KEY (event_id, measure_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE event_employee (
                event_id INTEGER NOT NULL,
                person_id INTEGER NOT NULL,
                involvement_type TEXT DEFAULT 'Victim',
                PRIMARY KEY (event_id, person_id)
            )
        """)
        
        logging.info("Structure créée. Insertion des données...")
        
        # Insérer les données de toutes les tables
        tables_data = [
            ('person', 'INSERT INTO person VALUES (?, ?, ?, ?, ?)'),
            ('organizational_unit', 'INSERT INTO organizational_unit VALUES (?, ?, ?, ?)'),
            ('risk', 'INSERT INTO risk VALUES (?, ?, ?, ?)'),
            ('corrective_measure', 'INSERT INTO corrective_measure VALUES (?, ?, ?, ?, ?, ?, ?)'),
            ('event', 'INSERT INTO event VALUES (?, ?, ?, ?, ?, ?, ?, ?)'),
            ('event_risk', 'INSERT INTO event_risk VALUES (?, ?)'),
            ('event_corrective_measure', 'INSERT INTO event_corrective_measure VALUES (?, ?)'),
            ('event_employee', 'INSERT INTO event_employee VALUES (?, ?, ?)'),
        ]
        
        for table_name, insert_query in tables_data:
            data = extract_copy_data(content, table_name)
            if data:
                cursor.executemany(insert_query, data)
                logging.info(f"✓ {len(data)} lignes insérées dans {table_name}")
            else:
                logging.warning(f"⚠ Aucune donnée trouvée pour {table_name}")
        
        conn.commit()
        conn.close()
        logging.info("\nBase de données créée avec succès!\n")
        return True
        
    except Exception as e:
        logging.error(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def export_tables():
    """Exporte chaque table vers un fichier CSV."""
    if not os.path.exists(DB_PATH):
        logging.error(f"Base {DB_PATH} non trouvée!")
        return
    
    # Créer le dossier de sortie
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Récupérer toutes les tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    logging.info(f"Export des tables vers {OUTPUT_DIR}/\n")
    logging.info(f"Tables trouvées: {', '.join(tables)}\n")
    
    files_created = []
    total_rows = 0
    
    for table in tables:
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        
        if rows:
            headers = [desc[0] for desc in cursor.description]
            csv_file = os.path.join(OUTPUT_DIR, f"{table}.csv")
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv_module.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            
            logging.info(f"✓ {table}.csv - {len(rows)} lignes")
            files_created.append(f"{table}.csv")
            total_rows += len(rows)
        else:
            logging.warning(f"⚠ {table} est vide")
    
    # Créer une vue enrichie des mesures correctives
    try:
        cursor.execute("""
            SELECT 
              cm.measure_id,
              cm.name,
              cm.description,
              cm.implementation_date,
              cm.cost,
              ou.name AS unit_name,
              ou.location,
              p.name AS owner_name,
              p.family_name AS owner_family_name
            FROM corrective_measure cm
            LEFT JOIN organizational_unit ou ON cm.organizational_unit_id = ou.unit_id
            LEFT JOIN person p ON cm.owner_id = p.person_id
        """)
        
        rows = cursor.fetchall()
        if rows:
            headers = [desc[0] for desc in cursor.description]
            csv_file = os.path.join(OUTPUT_DIR, "measures_enriched.csv")
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv_module.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            
            logging.info(f"\n✓ measures_enriched.csv - {len(rows)} lignes (vue enrichie)")
            files_created.append("measures_enriched.csv")
    except Exception as e:
        logging.warning(f"Impossible de créer la vue enrichie des mesures: {e}")
    
    # Créer une vue enrichie des événements
    try:
        cursor.execute("""
            SELECT 
              e.event_id,
              e.description AS event_description,
              e.start_datetime,
              e.end_datetime,
              e.type AS event_type,
              e.classification AS event_classification,
              p.name AS declarant_name,
              p.family_name AS declarant_family_name,
              p.matricule AS declarant_matricule,
              ou.name AS unit_name,
              ou.location AS unit_location,
              ou.identifier AS unit_identifier,
              r.name AS risk_name,
              r.gravity AS risk_gravity,
              r.probability AS risk_probability,
              cm.name AS corrective_measure_name,
              cm.description AS corrective_measure_description,
              cm.cost AS corrective_measure_cost
            FROM event e
            LEFT JOIN person p ON e.declared_by_id = p.person_id
            LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
            LEFT JOIN event_risk er ON e.event_id = er.event_id
            LEFT JOIN risk r ON er.risk_id = r.risk_id
            LEFT JOIN event_corrective_measure ecm ON e.event_id = ecm.event_id
            LEFT JOIN corrective_measure cm ON ecm.measure_id = cm.measure_id
        """)
        
        rows = cursor.fetchall()
        if rows:
            headers = [desc[0] for desc in cursor.description]
            csv_file = os.path.join(OUTPUT_DIR, "events_enriched.csv")
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv_module.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            
            logging.info(f"✓ events_enriched.csv - {len(rows)} lignes (vue complète événements)")
            files_created.append("events_enriched.csv")
    except Exception as e:
        logging.warning(f"Impossible de créer la vue enrichie des événements: {e}")
    
    conn.close()
    
    # Résumé
    logging.info(f"\n{'='*60}")
    logging.info("EXPORTATION TERMINÉE")
    logging.info("="*60)
    logging.info(f"✓ {len(files_created)} fichiers CSV créés")
    logging.info(f"✓ {total_rows} lignes totales exportées")
    logging.info(f"✓ Emplacement: {os.path.abspath(OUTPUT_DIR)}")
    logging.info("\nFichiers créés pour AWS RAG:")
    for file in files_created:
        logging.info(f"  - {file}")
    logging.info("="*60)

def main():
    logging.info("="*60)
    logging.info("EXPORTATION CSV POUR AWS RAG")
    logging.info("="*60 + "\n")
    
    if create_full_database():
        export_tables()
    else:
        logging.error("Échec de la création de la base de données")
        sys.exit(1)

if __name__ == "__main__":
    main()

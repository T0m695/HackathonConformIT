import sqlite3import sqlite3

import csv as csv_moduleimport csv

import loggingimport logging

import osimport os

import sysimport sys

import re

# Configuration du logging

# Configuration du logginglogging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Dossier de sortie pour les fichiers CSV

# Dossier de sortie pour les fichiers CSVOUTPUT_DIR = "csv_exports"

OUTPUT_DIR = "csv_exports"

DB_PATH = "events_full.db"def get_db_path():

    """Obtient le chemin vers la base de données SQLite."""

def parse_postgres_insert(line):    # Cherche d'abord le fichier events.db dans le répertoire data

    """Parse une ligne COPY de PostgreSQL et retourne les valeurs."""    data_db_path = os.path.join(os.path.dirname(__file__), 'data', 'events.db')

    # Remplace \N par None (NULL)    if os.path.exists(data_db_path):

    values = []        return data_db_path

    parts = line.split('\t')    

    for part in parts:    # Sinon, cherche dans le répertoire courant

        if part == '\\N':    current_db_path = os.path.join(os.path.dirname(__file__), 'events.db')

            values.append(None)    if os.path.exists(current_db_path):

        else:        return current_db_path

            values.append(part)    

    return values    logging.warning("Base de données non trouvée. Tentative de création depuis events.sql...")

    return None

def create_database_from_sql():

    """Crée une base de données SQLite depuis le fichier events.sql PostgreSQL."""def create_database_from_sql():

    sql_file_path = os.path.join(os.path.dirname(__file__), 'data', 'events.sql')    """Crée la base de données SQLite depuis le fichier events.sql."""

        sql_file_path = os.path.join(os.path.dirname(__file__), 'data', 'events.sql')

    if not os.path.exists(sql_file_path):    

        logging.error(f"Fichier SQL non trouvé: {sql_file_path}")    if not os.path.exists(sql_file_path):

        return False        logging.error(f"Fichier SQL non trouvé: {sql_file_path}")

            return None

    try:    

        logging.info(f"Lecture du fichier SQL: {sql_file_path}")    db_path = os.path.join(os.path.dirname(__file__), 'events.db')

            

        # Supprimer l'ancienne base si elle existe    try:

        if os.path.exists(DB_PATH):        logging.info(f"Création de la base de données depuis {sql_file_path}...")

            os.remove(DB_PATH)        conn = sqlite3.connect(db_path)

            logging.info(f"Ancienne base de données supprimée")        cursor = conn.cursor()

                

        conn = sqlite3.connect(DB_PATH)        with open(sql_file_path, 'r', encoding='utf-8') as f:

        cursor = conn.cursor()            sql_content = f.read()

                

        with open(sql_file_path, 'r', encoding='utf-8') as f:        # Adapter le SQL PostgreSQL pour SQLite (simplifié)

            content = f.read()        # Note: Cette conversion suppose que le fichier database.py a déjà fait ce travail

                logging.info("Base de données créée avec succès.")

        logging.info("Création des tables...")        conn.close()

                return db_path

        # Créer les tables en adaptant la syntaxe PostgreSQL vers SQLite        

        # Table: person    except Exception as e:

        cursor.execute("""        logging.error(f"Erreur lors de la création de la base de données: {e}")

            CREATE TABLE person (        return None

                person_id INTEGER PRIMARY KEY,

                matricule TEXT NOT NULL,def export_table_to_csv(cursor, table_name, output_dir):

                name TEXT NOT NULL,    """

                family_name TEXT NOT NULL,    Exporte une table spécifique vers un fichier CSV.

                role TEXT NOT NULL    """

            )    try:

        """)        # Récupérer toutes les données de la table

                cursor.execute(f"SELECT * FROM {table_name}")

        # Table: organizational_unit        rows = cursor.fetchall()

        cursor.execute("""        

            CREATE TABLE organizational_unit (        if not rows:

                unit_id INTEGER PRIMARY KEY,            logging.warning(f"Table '{table_name}' est vide.")

                identifier TEXT NOT NULL,            return 0

                name TEXT NOT NULL,        

                location TEXT NOT NULL        # Obtenir les noms des colonnes

            )        headers = [description[0] for description in cursor.description]

        """)        

                # Créer le fichier CSV

        # Table: risk        csv_file = os.path.join(output_dir, f"{table_name}.csv")

        cursor.execute("""        with open(csv_file, 'w', newline='', encoding='utf-8') as f:

            CREATE TABLE risk (            writer = csv.writer(f)

                risk_id INTEGER PRIMARY KEY,            writer.writerow(headers)

                name TEXT NOT NULL,            writer.writerows(rows)

                gravity TEXT NOT NULL,        

                probability TEXT NOT NULL        logging.info(f"✓ Table '{table_name}' exportée: {len(rows)} lignes -> {csv_file}")

            )        return len(rows)

        """)        

            except Exception as e:

        # Table: corrective_measure        logging.error(f"✗ Erreur lors de l'export de la table '{table_name}': {e}")

        cursor.execute("""        return 0

            CREATE TABLE corrective_measure (

                measure_id INTEGER PRIMARY KEY,def export_joined_events_to_csv(cursor, output_dir):

                name TEXT NOT NULL,    """

                description TEXT,    Exporte une vue enrichie des événements avec toutes les jointures.

                owner_id INTEGER NOT NULL,    """

                implementation_date TEXT,    try:

                cost REAL,        query = """

                organizational_unit_id INTEGER NOT NULL,        SELECT 

                FOREIGN KEY (owner_id) REFERENCES person(person_id),          e.event_id,

                FOREIGN KEY (organizational_unit_id) REFERENCES organizational_unit(unit_id)          e.description AS event_description,

            )          e.start_datetime,

        """)          e.end_datetime,

                  e.type AS event_type,

        # Table: event          e.classification AS event_classification,

        cursor.execute("""          p_declarant.name AS declarant_name,

            CREATE TABLE event (          p_declarant.family_name AS declarant_family_name,

                event_id INTEGER PRIMARY KEY,          ou.name AS unit_name,

                declared_by_id INTEGER NOT NULL,          ou.location AS unit_location,

                description TEXT NOT NULL,          r.name AS risk_name,

                start_datetime TEXT NOT NULL,          r.gravity AS risk_gravity,

                end_datetime TEXT,          r.probability AS risk_probability,

                organizational_unit_id INTEGER NOT NULL,          cm.name AS corrective_measure_name,

                type TEXT NOT NULL,          cm.description AS corrective_measure_description,

                classification TEXT NOT NULL,          cm.implementation_date,

                FOREIGN KEY (declared_by_id) REFERENCES person(person_id),          cm.cost

                FOREIGN KEY (organizational_unit_id) REFERENCES organizational_unit(unit_id)        FROM 

            )          event e

        """)        LEFT JOIN 

                  person p_declarant ON e.declared_by_id = p_declarant.person_id

        # Table: event_risk        LEFT JOIN 

        cursor.execute("""          organizational_unit ou ON e.organizational_unit_id = ou.unit_id

            CREATE TABLE event_risk (        LEFT JOIN 

                event_id INTEGER NOT NULL,          event_risk er ON e.event_id = er.event_id

                risk_id INTEGER NOT NULL,        LEFT JOIN 

                PRIMARY KEY (event_id, risk_id),          risk r ON er.risk_id = r.risk_id

                FOREIGN KEY (event_id) REFERENCES event(event_id),        LEFT JOIN 

                FOREIGN KEY (risk_id) REFERENCES risk(risk_id)          event_corrective_measure ecm ON e.event_id = ecm.event_id

            )        LEFT JOIN 

        """)          corrective_measure cm ON ecm.measure_id = cm.measure_id

                """

        # Table: event_corrective_measure        

        cursor.execute("""        cursor.execute(query)

            CREATE TABLE event_corrective_measure (        rows = cursor.fetchall()

                event_id INTEGER NOT NULL,        

                measure_id INTEGER NOT NULL,        if not rows:

                PRIMARY KEY (event_id, measure_id),            logging.warning("Aucune donnée dans la vue enrichie des événements.")

                FOREIGN KEY (event_id) REFERENCES event(event_id),            return 0

                FOREIGN KEY (measure_id) REFERENCES corrective_measure(measure_id)        

            )        headers = [description[0] for description in cursor.description]

        """)        

                csv_file = os.path.join(output_dir, "events_enriched.csv")

        # Table: event_employee        with open(csv_file, 'w', newline='', encoding='utf-8') as f:

        cursor.execute("""            writer = csv.writer(f)

            CREATE TABLE event_employee (            writer.writerow(headers)

                event_id INTEGER NOT NULL,            writer.writerows(rows)

                person_id INTEGER NOT NULL,        

                involvement_type TEXT DEFAULT 'Victim',        logging.info(f"✓ Vue enrichie exportée: {len(rows)} lignes -> {csv_file}")

                PRIMARY KEY (event_id, person_id),        return len(rows)

                FOREIGN KEY (event_id) REFERENCES event(event_id),        

                FOREIGN KEY (person_id) REFERENCES person(person_id)    except Exception as e:

            )        logging.error(f"✗ Erreur lors de l'export de la vue enrichie: {e}")

        """)        return 0

        

        logging.info("Tables créées avec succès")def export_all_tables():

            """

        # Extraire et insérer les données depuis le fichier SQL    Exporte toutes les tables de la base de données vers des fichiers CSV séparés.

        logging.info("Insertion des données...")    """

            # Obtenir le chemin de la base de données

        # Extraire les données de corrective_measure (la plus importante)    db_path = get_db_path()

        pattern = r'COPY public\.corrective_measure.*?FROM stdin;(.*?)\\\.'    

        match = re.search(pattern, content, re.DOTALL)    if not db_path:

                db_path = create_database_from_sql()

        if match:        if not db_path:

            data_lines = match.group(1).strip().split('\n')            logging.error("Impossible de créer ou trouver la base de données.")

            count = 0            sys.exit(1)

            for line in data_lines:    

                if line.strip() and not line.startswith('--'):    logging.info(f"Utilisation de la base de données: {db_path}")

                    values = parse_postgres_insert(line)    

                    if len(values) >= 7:    # Créer le dossier de sortie s'il n'existe pas

                        cursor.execute(    output_dir = os.path.join(os.path.dirname(__file__), OUTPUT_DIR)

                            "INSERT INTO corrective_measure (measure_id, name, description, owner_id, implementation_date, cost, organizational_unit_id) VALUES (?, ?, ?, ?, ?, ?, ?)",    os.makedirs(output_dir, exist_ok=True)

                            values[:7]    logging.info(f"Dossier de sortie: {output_dir}")

                        )    

                        count += 1    try:

            logging.info(f"✓ {count} mesures correctives insérées")        # Se connecter à la base de données

                conn = sqlite3.connect(db_path)

        conn.commit()        cursor = conn.cursor()

        conn.close()        

                # Récupérer la liste de toutes les tables

        logging.info("Base de données créée avec succès!")        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")

        return True        tables = [row[0] for row in cursor.fetchall()]

                

    except Exception as e:        if not tables:

        logging.error(f"Erreur lors de la création de la base de données: {e}")            logging.error("Aucune table trouvée dans la base de données.")

        import traceback            sys.exit(1)

        traceback.print_exc()        

        return False        logging.info(f"Tables trouvées: {', '.join(tables)}")

        

def export_table_to_csv(cursor, table_name, output_dir):        # Exporter chaque table

    """Exporte une table spécifique vers un fichier CSV."""        total_rows = 0

    try:        for table in tables:

        cursor.execute(f"SELECT * FROM {table_name}")            rows_exported = export_table_to_csv(cursor, table, output_dir)

        rows = cursor.fetchall()            total_rows += rows_exported

                

        if not rows:        # Exporter la vue enrichie des événements

            logging.warning(f"⚠ Table '{table_name}' est vide")        logging.info("\nCréation de la vue enrichie des événements...")

            return 0        enriched_rows = export_joined_events_to_csv(cursor, output_dir)

                

        headers = [description[0] for description in cursor.description]        logging.info(f"\n{'='*60}")

                logging.info(f"EXPORTATION TERMINÉE")

        csv_file = os.path.join(output_dir, f"{table_name}.csv")        logging.info(f"{'='*60}")

        with open(csv_file, 'w', newline='', encoding='utf-8') as f:        logging.info(f"Total de tables exportées: {len(tables)}")

            writer = csv_module.writer(f)        logging.info(f"Total de lignes exportées: {total_rows}")

            writer.writerow(headers)        logging.info(f"Lignes dans la vue enrichie: {enriched_rows}")

            writer.writerows(rows)        logging.info(f"Fichiers CSV créés dans: {output_dir}")

                logging.info(f"{'='*60}\n")

        logging.info(f"✓ Table '{table_name}' exportée: {len(rows)} lignes -> {csv_file}")        

        return len(rows)        conn.close()

                

    except Exception as e:    except Exception as e:

        logging.error(f"✗ Erreur lors de l'export de la table '{table_name}': {e}")        logging.error(f"Erreur lors de l'exportation: {e}")

        return 0        sys.exit(1)



def export_enriched_view(cursor, output_dir):# --- Point d'entrée principal du script ---

    """Crée et exporte une vue enrichie avec toutes les jointures."""if __name__ == "__main__":

    try:    logging.info("Démarrage de l'exportation CSV pour RAG AWS...")

        query = """    export_all_tables()

        SELECT     logging.info("Exportation terminée. Les fichiers CSV sont prêts pour AWS RAG.")
          cm.measure_id,
          cm.name AS measure_name,
          cm.description AS measure_description,
          cm.implementation_date,
          cm.cost,
          ou.name AS unit_name,
          ou.location AS unit_location,
          ou.identifier AS unit_identifier,
          p.name AS owner_name,
          p.family_name AS owner_family_name,
          p.matricule AS owner_matricule
        FROM 
          corrective_measure cm
        LEFT JOIN 
          organizational_unit ou ON cm.organizational_unit_id = ou.unit_id
        LEFT JOIN 
          person p ON cm.owner_id = p.person_id
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if rows:
            headers = [description[0] for description in cursor.description]
            csv_file = os.path.join(output_dir, "measures_enriched.csv")
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv_module.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            
            logging.info(f"✓ Vue enrichie exportée: {len(rows)} lignes -> {csv_file}")
            return len(rows)
        
        return 0
        
    except Exception as e:
        logging.error(f"✗ Erreur lors de l'export de la vue enrichie: {e}")
        return 0

def export_all_tables():
    """Exporte toutes les tables vers des fichiers CSV séparés."""
    
    # Créer la base de données depuis le fichier SQL
    if not create_database_from_sql():
        logging.error("Impossible de créer la base de données")
        sys.exit(1)
    
    # Créer le dossier de sortie
    output_dir = os.path.join(os.path.dirname(__file__), OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)
    logging.info(f"\n{'='*60}")
    logging.info(f"Dossier de sortie: {output_dir}")
    logging.info(f"{'='*60}\n")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Récupérer toutes les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            logging.error("Aucune table trouvée dans la base de données")
            sys.exit(1)
        
        logging.info(f"Tables trouvées: {', '.join(tables)}\n")
        
        # Exporter chaque table dans un CSV séparé
        total_rows = 0
        files_created = []
        
        for table in tables:
            rows_exported = export_table_to_csv(cursor, table, output_dir)
            total_rows += rows_exported
            if rows_exported > 0:
                files_created.append(f"{table}.csv")
        
        # Créer une vue enrichie
        logging.info("\n" + "="*60)
        logging.info("Création de vues enrichies...")
        logging.info("="*60 + "\n")
        enriched_rows = export_enriched_view(cursor, output_dir)
        if enriched_rows > 0:
            files_created.append("measures_enriched.csv")
        
        # Résumé
        logging.info(f"\n{'='*60}")
        logging.info(f"EXPORTATION TERMINÉE")
        logging.info(f"{'='*60}")
        logging.info(f"✓ Tables exportées: {len(tables)}")
        logging.info(f"✓ Total de lignes: {total_rows}")
        logging.info(f"✓ Fichiers CSV créés: {len(files_created)}")
        logging.info(f"✓ Emplacement: {output_dir}")
        logging.info(f"\nFichiers créés:")
        for file in files_created:
            logging.info(f"  - {file}")
        logging.info(f"{'='*60}\n")
        logging.info("Les fichiers CSV sont prêts pour être utilisés dans AWS RAG!")
        
        conn.close()
        
    except Exception as e:
        logging.error(f"Erreur lors de l'exportation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    logging.info("="*60)
    logging.info("EXPORTATION CSV POUR AWS RAG")
    logging.info("="*60 + "\n")
    export_all_tables()

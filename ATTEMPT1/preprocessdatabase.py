"""
Prétraitement du fichier SQL pour générer un fichier schema.json
avec des descriptions et synonymes générés par IA.
"""

import json
import re
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
import logging

from bedrock_utils import invoke_llm, invoke_embedding

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ColumnInfo:
    """Information sur une colonne de la base de données."""
    name: str
    data_type: str
    description: str = ""
    synonyms: List[str] = None
    sample_values: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.synonyms is None:
            self.synonyms = []

@dataclass
class TableInfo:
    """Information sur une table de la base de données."""
    name: str
    columns: List[ColumnInfo]
    description: str = ""
    sample_data: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Relationship:
    """Information sur une relation entre tables."""
    from_table: str
    to_table: str
    on_column: str
    type: str = "foreign_key"
    description: str = ""

class DatabasePreprocessor:
    """Classe pour prétraiter le fichier SQL et générer le schema.json."""
    
    def __init__(self, sql_file: str):
        """Initialise le préprocesseur avec le chemin du fichier SQL."""
        self.sql_file = sql_file
        self.tables: List[TableInfo] = []
        self.relationships: List[Relationship] = []

    def extract_sample_data(self, sql_content: str) -> None:
        """Extrait les données d'exemple depuis les INSERT statements."""
        print(f"\n📊 Extraction des données d'exemple...")
        
        for table in self.tables:
            # Chercher plusieurs formats d'INSERT
            patterns = [
                # INSERT INTO table VALUES (...)
                rf"INSERT INTO\s+(?:public\.)?{table.name}\s+VALUES\s*\((.*?)\);",
                # INSERT INTO public.table VALUES (...)
                rf"INSERT INTO\s+public\.{table.name}\s+VALUES\s*\((.*?)\);",
                # COPY table FROM stdin avec données
                rf"COPY\s+(?:public\.)?{table.name}\s+.*?FROM stdin;(.*?)\\.",
            ]
            
            all_inserts = []
            for pattern in patterns:
                matches = list(re.finditer(pattern, sql_content, re.IGNORECASE | re.DOTALL))
                if matches:
                    print(f"  🔍 Pattern trouvé pour {table.name}: {len(matches)} entrées")
                    all_inserts.extend(matches)
                    if len(all_inserts) >= 10:
                        break
            
            if not all_inserts:
                print(f"  ⚠️  {table.name}: Aucune donnée trouvée. Cherchons manuellement...")
                # Recherche manuelle
                idx = sql_content.lower().find(f"insert into {table.name.lower()}")
                if idx == -1:
                    idx = sql_content.lower().find(f"insert into public.{table.name.lower()}")
                if idx == -1:
                    idx = sql_content.lower().find(f"copy {table.name.lower()}")
                if idx != -1:
                    print(f"     Trouvé à position {idx}, échantillon:")
                    print(f"     {sql_content[idx:idx+200]}")
            
            samples = []
            for i, insert_match in enumerate(all_inserts[:10]):
                values_text = insert_match.group(1).strip()
                
                # Si c'est un COPY, on parse différemment (lignes séparées par \n)
                if '\n' in values_text or '\t' in values_text:
                    lines = values_text.split('\n')
                    for line in lines[:10]:
                        if not line.strip():
                            continue
                        # Format COPY: valeurs séparées par \t
                        values = [v.strip() for v in line.split('\t')]
                        if len(values) == len(table.columns):
                            row = {}
                            for col, val in zip(table.columns, values):
                                row[col.name] = val
                                if len(col.sample_values) < 10 and val and val != '\\N':
                                    col.sample_values.append(val)
                            samples.append(row)
                else:
                    # Parser les valeurs INSERT classiques
                    values = []
                    current_val = ""
                    in_quotes = False
                    quote_char = None
                    paren_depth = 0
                    
                    for char in values_text:
                        if char in ("'", '"') and (not in_quotes or char == quote_char):
                            if in_quotes:
                                in_quotes = False
                                quote_char = None
                            else:
                                in_quotes = True
                                quote_char = char
                            current_val += char
                        elif char == '(' and not in_quotes:
                            paren_depth += 1
                            current_val += char
                        elif char == ')' and not in_quotes:
                            paren_depth -= 1
                            current_val += char
                        elif char == ',' and not in_quotes and paren_depth == 0:
                            values.append(current_val.strip().strip("'\""))
                            current_val = ""
                        else:
                            current_val += char
                    
                    if current_val:
                        values.append(current_val.strip().strip("'\""))
                    
                    # Créer un dict avec les noms de colonnes
                    if len(values) == len(table.columns):
                        row = {}
                        for col, val in zip(table.columns, values):
                            row[col.name] = val
                            if len(col.sample_values) < 10 and val and val.upper() != 'NULL':
                                col.sample_values.append(val)
                        samples.append(row)
            
            table.sample_data = samples
            print(f"  ✅ {table.name}: {len(samples)} exemples extraits")

    def extract_relationships(self, sql_content: str) -> None:
        """Extrait les relations (foreign keys) depuis le SQL."""
        print(f"\n🔗 Extraction des relations entre tables...")
        
        # Pattern pour FOREIGN KEY dans les CREATE TABLE
        fk_pattern = r"(?:CONSTRAINT\s+\w+\s+)?FOREIGN KEY\s*\((\w+)\)\s+REFERENCES\s+(?:public\.)?(\w+)\s*\((\w+)\)"
        
        # Aussi chercher les ALTER TABLE ADD CONSTRAINT
        alter_fk_pattern = r"ALTER TABLE\s+(?:ONLY\s+)?(?:public\.)?(\w+)\s+ADD CONSTRAINT.*?FOREIGN KEY\s*\((\w+)\)\s+REFERENCES\s+(?:public\.)?(\w+)\s*\((\w+)\)"
        
        # Chercher dans CREATE TABLE
        matches = list(re.finditer(fk_pattern, sql_content, re.IGNORECASE))
        print(f"  🔍 {len(matches)} FK trouvées dans CREATE TABLE")
        
        for match in matches:
            from_col = match.group(1)
            to_table = match.group(2)
            to_col = match.group(3)
            
            # Trouver la table source en cherchant le CREATE TABLE précédent
            start_pos = match.start()
            # Chercher en arrière le dernier CREATE TABLE
            search_text = sql_content[:start_pos]
            create_matches = list(re.finditer(r"CREATE TABLE\s+(?:public\.)?(\w+)", search_text, re.IGNORECASE))
            
            if create_matches:
                from_table = create_matches[-1].group(1)  # Prendre le dernier match
                
                rel = Relationship(
                    from_table=from_table,
                    to_table=to_table,
                    on_column=from_col,
                    type="foreign_key"
                )
                self.relationships.append(rel)
                print(f"  ✅ {from_table}.{from_col} → {to_table}.{to_col}")
        
        # Chercher dans ALTER TABLE
        alter_matches = list(re.finditer(alter_fk_pattern, sql_content, re.IGNORECASE))
        print(f"  🔍 {len(alter_matches)} FK trouvées dans ALTER TABLE")
        
        for match in alter_matches:
            from_table = match.group(1)
            from_col = match.group(2)
            to_table = match.group(3)
            to_col = match.group(4)
            
            rel = Relationship(
                from_table=from_table,
                to_table=to_table,
                on_column=from_col,
                type="foreign_key"
            )
            self.relationships.append(rel)
            print(f"  ✅ {from_table}.{from_col} → {to_table}.{to_col}")
        
        print(f"  📊 Total: {len(self.relationships)} relations trouvées")
    
    def _validate_relationships(self) -> None:
        """Valide que les relations pointent vers des colonnes existantes."""
        print(f"\n✅ Validation des relations...")
        
        # Créer un mapping table -> colonnes
        table_columns = {}
        for table in self.tables:
            table_columns[table.name] = {col.name for col in table.columns}
        
        valid_relationships = []
        invalid_count = 0
        
        for rel in self.relationships:
            is_valid = True
            
            # Vérifier que la table source existe
            if rel.from_table not in table_columns:
                print(f"  ❌ Table source inexistante: {rel.from_table}")
                is_valid = False
            # Vérifier que la table cible existe
            elif rel.to_table not in table_columns:
                print(f"  ❌ Table cible inexistante: {rel.to_table}")
                is_valid = False
            # Vérifier que la colonne existe dans la table source
            elif rel.on_column not in table_columns[rel.from_table]:
                print(f"  ❌ Colonne {rel.on_column} n'existe pas dans {rel.from_table}")
                is_valid = False
            else:
                valid_relationships.append(rel)
        
        invalid_count = len(self.relationships) - len(valid_relationships)
        self.relationships = valid_relationships
        
        print(f"  ✅ Relations valides: {len(valid_relationships)}")
        if invalid_count > 0:
            print(f"  ⚠️  Relations invalides supprimées: {invalid_count}")

    def extract_schema(self) -> None:
        """Extrait la structure depuis le fichier SQL."""
        try:
            print(f"\n🔍 Lecture du fichier SQL : {self.sql_file}")
            with open(self.sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            print(f"✅ Fichier lu : {len(sql_content)} caractères")
            
            # Afficher un échantillon
            print(f"\n📄 Échantillon du fichier (1000 premiers caractères) :")
            print("-" * 60)
            print(sql_content[:1000])
            print("-" * 60)
            
            # Chercher les CREATE TABLE
            create_positions = [m.start() for m in re.finditer(r'CREATE TABLE', sql_content, re.IGNORECASE)]
            print(f"\n🔎 Positions 'CREATE TABLE' trouvées : {len(create_positions)}")
            if create_positions:
                print(f"   Premières positions : {create_positions[:5]}")
                if create_positions[0] < len(sql_content):
                    start = max(0, create_positions[0] - 100)
                    end = min(len(sql_content), create_positions[0] + 500)
                    print(f"\n📋 Échantillon autour du premier CREATE TABLE :")
                    print("-" * 60)
                    print(sql_content[start:end])
                    print("-" * 60)

            # Essayer plusieurs patterns
            patterns = [
                (r"CREATE TABLE\s+(\w+)\s*\(([\s\S]*?)\);", "Standard avec ;"),
                (r"CREATE TABLE\s+(?:public\.)?(\w+)\s*\(([\s\S]*?)\);", "Avec public. et ;"),
                (r"CREATE TABLE\s+(?:public\.)?(\w+)\s+\(\s*([\s\S]*?)\s*\);", "Multiline avec espaces"),
            ]
            
            tables_found = []
            for pattern, desc in patterns:
                print(f"\n🔍 Essai pattern : {desc}")
                tables = list(re.finditer(pattern, sql_content, re.IGNORECASE))
                print(f"   ✅ {len(tables)} tables trouvées")
                if len(tables) > 0:
                    tables_found = tables
                    print(f"   🎯 Pattern retenu : {desc}")
                    break

            if len(tables_found) == 0:
                print("\n⚠️  DIAGNOSTIC : Aucun pattern ne fonctionne.")
                lines = sql_content.split('\n')
                for i, line in enumerate(lines[:100]):
                    if 'CREATE TABLE' in line.upper():
                        print(f"\n📍 Ligne {i}: {line}")
                        print("   Contexte (10 lignes suivantes):")
                        for j in range(i, min(i+10, len(lines))):
                            print(f"   {j}: {lines[j][:100]}")
                        break
                raise ValueError("Impossible de trouver des CREATE TABLE")

            # Parser les tables
            for i, table_match in enumerate(tables_found):
                table_name = table_match.group(1)
                columns_text = table_match.group(2)
                
                print(f"\n--- Table {i+1}: {table_name} ---")
                
                # Pattern pour colonnes PostgreSQL
                column_patterns = [
                    (r'^\s*(\w+)\s+((?:character varying|varchar|integer|int|text|timestamp|numeric|boolean|date|jsonb|smallint|bigint)(?:\([^)]+\))?)', "Standard"),
                ]
                
                column_infos = []
                for pattern, desc in column_patterns:
                    columns = list(re.finditer(pattern, columns_text, re.MULTILINE | re.IGNORECASE))
                    
                    if len(columns) > 0:
                        for col_match in columns:
                            col_name = col_match.group(1)
                            data_type_raw = col_match.group(2).strip()
                            
                            # Normaliser les types
                            data_type = data_type_raw.upper()
                            if 'CHARACTER VARYING' in data_type or 'VARCHAR' in data_type:
                                data_type = 'VARCHAR'
                            elif 'INTEGER' in data_type or data_type.startswith('INT'):
                                data_type = 'INTEGER'
                            elif 'TIMESTAMP' in data_type:
                                data_type = 'TIMESTAMP'
                            elif 'NUMERIC' in data_type:
                                data_type = 'NUMERIC'
                            elif 'TEXT' in data_type:
                                data_type = 'TEXT'
                            elif 'BOOLEAN' in data_type:
                                data_type = 'BOOLEAN'
                            elif 'DATE' in data_type:
                                data_type = 'DATE'
                            elif 'JSONB' in data_type:
                                data_type = 'JSONB'
                            else:
                                data_type = data_type.split()[0].upper()
                            
                            if col_name.upper() not in ['CONSTRAINT', 'PRIMARY', 'FOREIGN', 'KEY', 'UNIQUE', 'CHECK']:
                                column_infos.append(ColumnInfo(
                                    name=col_name,
                                    data_type=data_type
                                ))
                        break
                
                print(f"  ✅ {len(column_infos)} colonnes trouvées")
                
                if column_infos:
                    table_info = TableInfo(
                        name=table_name,
                        columns=column_infos
                    )
                    self.tables.append(table_info)

            print(f"\n📊 RÉSUMÉ : {len(self.tables)} tables extraites")
            
            # Extraire les données d'exemple
            self.extract_sample_data(sql_content)
            
            # Extraire les relations
            self.extract_relationships(sql_content)
            
            # Valider les relations
            self._validate_relationships()
            
            logger.info(f"Extrait le schéma de {len(self.tables)} tables")
            
        except Exception as e:
            print(f"❌ ERREUR : {e}")
            import traceback
            traceback.print_exc()
            raise

    def generate_descriptions(self) -> None:
        """Génère les descriptions et synonymes en utilisant l'IA."""
        print(f"\n🤖 Génération des descriptions IA pour {len(self.tables)} tables...")
        
        for idx, table in enumerate(self.tables):
            print(f"\n--- Table {idx+1}/{len(self.tables)}: {table.name} ---")
            
            # Préparer le contexte avec exemples
            columns_desc = ', '.join(col.name for col in table.columns)
            context = f"Colonnes: {columns_desc}"
            
            # Ajouter quelques exemples de données
            if table.sample_data:
                context += f"\n\nExemples de données (premières entrées):"
                for i, row in enumerate(table.sample_data[:3]):
                    context += f"\n  Exemple {i+1}: {row}"
            
            # Générer la description de la table - COURTE (1-2 phrases max)
            prompt = f"""Décris BRIÈVEMENT la table {table.name} en te basant sur ses colonnes et exemples :
            {context}
            
            Réponds en 1-2 phrases COURTES uniquement (maximum 150 caractères)."""
            
            try:
                print(f"  📝 Génération description table...")
                table.description = invoke_llm(prompt).strip()
                # Limiter à 200 caractères
                if len(table.description) > 200:
                    table.description = table.description[:197] + "..."
                print(f"  ✅ Description : {table.description}")

                # Générer les descriptions et synonymes des colonnes
                for col_idx, col in enumerate(table.columns):
                    print(f"    • Colonne {col_idx+1}/{len(table.columns)}: {col.name}")
                    
                    # Contexte avec exemples de valeurs
                    col_context = ""
                    if col.sample_values:
                        examples = col.sample_values[:5]
                        col_context = f"\nExemples de valeurs: {', '.join(str(v)[:50] for v in examples)}"
                    
                    # Prompt plus strict et structuré - COURTE DESCRIPTION
                    col_prompt = f"""Analyse cette colonne de base de données :
Nom: {col.name}
Type: {col.data_type}
Table: {table.name}{col_context}

Réponds EXACTEMENT dans ce format (1 PHRASE courte pour la description) :
Description: [une phrase courte décrivant l'utilité - MAX 100 caractères]
Synonyms: mot1, mot2, mot3, mot4

Exemple de bonne réponse:
Description: Identifiant unique de l'événement
Synonyms: id_événement, numéro_événement, référence, code"""
                    
                    # Essayer jusqu'à 2 fois
                    success = False
                    for attempt in range(2):
                        try:
                            response = invoke_llm(col_prompt).strip()
                            
                            # Parsing plus robuste
                            desc_part = None
                            syn_part = None
                            
                            # Méthode 1: Split classique
                            if "Description:" in response and "Synonyms:" in response:
                                parts = response.split("Synonyms:")
                                desc_part = parts[0].split("Description:")[-1].strip()
                                syn_part = parts[1].strip()
                            # Méthode 2: Regex plus permissive
                            elif "Description" in response:
                                desc_match = re.search(r"Description\s*:?\s*(.+?)(?=Synonym|$)", response, re.IGNORECASE | re.DOTALL)
                                syn_match = re.search(r"Synonym[s]?\s*:?\s*(.+?)$", response, re.IGNORECASE | re.DOTALL)
                                if desc_match:
                                    desc_part = desc_match.group(1).strip()
                                if syn_match:
                                    syn_part = syn_match.group(1).strip()
                            
                            # Nettoyer la description - COURT
                            if desc_part:
                                desc_part = desc_part.split('\n')[0]  # Première ligne seulement
                                if len(desc_part) > 150:
                                    desc_part = desc_part[:147] + "..."
                            
                            # Parser les synonymes
                            syn_list = []
                            if syn_part:
                                # Nettoyer et splitter
                                syn_part = syn_part.replace('\n', ',').replace(';', ',')
                                syn_list = [
                                    s.strip().strip('[]().-•*"\'') 
                                    for s in syn_part.split(",") 
                                    if s.strip()
                                ]
                                # Filtrer les synonymes valides (pas trop longs, pas de phrases)
                                syn_list = [
                                    s for s in syn_list 
                                    if len(s) > 0 and len(s) < 50 and s.count(' ') <= 2
                                ][:5]
                            
                            if desc_part and len(desc_part) > 10:
                                col.description = desc_part
                                col.synonyms = syn_list
                                print(f"      ✅ {len(syn_list)} synonymes")
                                success = True
                                break
                            else:
                                if attempt == 0:
                                    print(f"      ⚠️  Tentative {attempt+1} échouée, retry...")
                                    continue
                        
                        except Exception as e:
                            if attempt == 0:
                                print(f"      ⚠️  Erreur tentative {attempt+1}: {e}")
                                continue
                    
                    if not success:
                        print(f"      ❌ Échec après 2 tentatives, valeurs par défaut")
                        col.description = f"Colonne {col.name} de type {col.data_type}"
                        col.synonyms = []

            except Exception as e:
                print(f"  ❌ Erreur IA : {e}")
                continue
        
        # Générer descriptions des relations
        print(f"\n🔗 Génération des descriptions des relations...")
        
        # Dédupliquer les relations
        unique_relations = {}
        for rel in self.relationships:
            key = (rel.from_table, rel.to_table, rel.on_column)
            if key not in unique_relations:
                unique_relations[key] = rel
        
        self.relationships = list(unique_relations.values())
        print(f"  📊 {len(self.relationships)} relations uniques à décrire")
        
        for idx, rel in enumerate(self.relationships):
            print(f"  • Relation {idx+1}/{len(self.relationships)}: {rel.from_table} → {rel.to_table}")
            
            prompt = f"""Décris brièvement cette relation de base de données :
Table source: {rel.from_table}
Table cible: {rel.to_table}
Colonne de jointure: {rel.on_column}

Réponds en UNE phrase courte et claire (MAX 100 caractères)."""
            
            try:
                description = invoke_llm(prompt).strip()
                # Nettoyer la description - COURTE
                description = description.split('\n')[0]  # Prendre première ligne
                if len(description) > 150:
                    description = description[:147] + "..."
                rel.description = description
                print(f"    ✅ {description[:80]}...")
            except Exception as e:
                print(f"    ⚠️  Erreur: {e}")
                rel.description = f"Relation entre {rel.from_table} et {rel.to_table} via {rel.on_column}"

    def generate_schema_json(self) -> Dict[str, Any]:
        """Convertit la structure en format schema.json (FORMAT LISTE comme schema.json)."""
        print(f"\n📋 Génération du JSON final...")
        
        schema = {
            "tables": {},
            "relationships": [],
            "sample_queries": []
        }

        # Tables avec format LISTE pour les colonnes
        for table in self.tables:
            columns_list = []
            
            for col in table.columns:
                columns_list.append({
                    "name": col.name,
                    "type": col.data_type,
                    "synonyms": col.synonyms,
                    "description": col.description
                })
            
            schema["tables"][table.name] = {
                "columns": columns_list,  # FORMAT LISTE comme schema.json
                "description": table.description
            }

        # Relations
        for rel in self.relationships:
            schema["relationships"].append({
                "from": rel.from_table,
                "to": rel.to_table,
                "on": rel.on_column,
                "type": rel.type,
                "description": rel.description
            })

        # Générer quelques sample_queries basiques
        print(f"\n📝 Génération des requêtes SQL d'exemple...")
        schema["sample_queries"] = self._generate_sample_queries()

        print(f"✅ JSON généré avec {len(schema['tables'])} tables, {len(schema['relationships'])} relations, {len(schema['sample_queries'])} requêtes")
        return schema
    
    def _generate_sample_queries(self) -> List[Dict[str, str]]:
        """Génère des requêtes SQL d'exemple basiques."""
        queries = []
        
        # Vérifier quelles tables existent
        table_names = {t.name for t in self.tables}
        
        # Requête 1: Liste tous les événements si la table existe
        if "event" in table_names:
            event_table = next(t for t in self.tables if t.name == "event")
            event_cols = [c.name for c in event_table.columns]
            
            select_cols = []
            if "event_id" in event_cols:
                select_cols.append("event_id")
            if "type" in event_cols:
                select_cols.append("type")
            if "classification" in event_cols:
                select_cols.append("classification")
            if "start_datetime" in event_cols:
                select_cols.append("start_datetime")
            if "description" in event_cols:
                select_cols.append("description")
            
            if select_cols:
                queries.append({
                    "natural_language": "Liste tous les événements de 2024",
                    "sql": f"SELECT {', '.join(select_cols)} FROM event WHERE EXTRACT(YEAR FROM start_datetime) = 2024 ORDER BY start_datetime DESC LIMIT 100;"
                })
                
                queries.append({
                    "natural_language": "Compte les événements par type",
                    "sql": "SELECT type, COUNT(*) as nombre_evenements FROM event GROUP BY type ORDER BY nombre_evenements DESC;"
                })
        
        # Requête 2: Jointure event-person si les deux tables existent
        if "event" in table_names and "person" in table_names:
            queries.append({
                "natural_language": "Trouve les événements avec leurs déclarants",
                "sql": "SELECT e.event_id, e.description, e.start_datetime, p.name, p.family_name FROM event e JOIN person p ON e.declared_by_id = p.person_id ORDER BY e.start_datetime DESC LIMIT 50;"
            })
        
        # Requête 3: Mesures correctives
        if "corrective_measure" in table_names:
            queries.append({
                "natural_language": "Liste les mesures correctives avec leur coût",
                "sql": "SELECT name, description, cost, implementation_date FROM corrective_measure WHERE cost IS NOT NULL ORDER BY cost DESC LIMIT 100;"
            })
        
        # Requête 4: Risques
        if "risk" in table_names and "event" in table_names and "event_risk" in table_names:
            queries.append({
                "natural_language": "Trouve les événements avec risque de gravité HIGH",
                "sql": "SELECT e.event_id, e.type, e.description, r.name as risque, r.gravity FROM event e JOIN event_risk er ON e.event_id = er.event_id JOIN risk r ON er.risk_id = r.risk_id WHERE r.gravity = 'HIGH' LIMIT 100;"
            })
        
        # Requête 5: Unités organisationnelles
        if "organizational_unit" in table_names and "event" in table_names:
            queries.append({
                "natural_language": "Liste les événements par unité organisationnelle",
                "sql": "SELECT ou.name as unite, COUNT(e.event_id) as nombre_evenements FROM organizational_unit ou JOIN event e ON ou.unit_id = e.organizational_unit_id GROUP BY ou.name ORDER BY nombre_evenements DESC;"
            })
        
        return queries

    def process_and_save(self, output_file: str) -> None:
        """Traite la base de données et sauvegarde le schéma."""
        try:
            print("\n" + "="*60)
            print("🚀 DÉBUT DU PRÉTRAITEMENT")
            print("="*60)
            
            print("\n📖 ÉTAPE 1/3 : Extraction du schéma SQL")
            self.extract_schema()
            
            if len(self.tables) == 0:
                raise ValueError("❌ Aucune table extraite !")
            
            print("\n🤖 ÉTAPE 2/3 : Génération des descriptions IA")
            self.generate_descriptions()
            
            print("\n💾 ÉTAPE 3/3 : Sauvegarde du schéma")
            schema = self.generate_schema_json()
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ Schema sauvegardé dans {output_file}")
            print(f"📊 Statistiques finales :")
            print(f"   - Tables : {len(schema['tables'])}")
            total_cols = sum(len(t['columns']) for t in schema['tables'].values())
            print(f"   - Colonnes : {total_cols}")
            print(f"   - Relations : {len(schema['relationships'])}")
            
            print("\n" + "="*60)
            print("✨ PRÉTRAITEMENT TERMINÉ AVEC SUCCÈS")
            print("="*60)

        except Exception as e:
            print(f"\n❌ ERREUR FATALE : {e}")
            raise

def main():
    """Point d'entrée principal."""
    try:
        sql_file = "../data/events-bis.sql"
        
        print(f"🎯 Fichier source : {sql_file}")
        print(f"🎯 Fichier destination : schema2.json")
        
        preprocessor = DatabasePreprocessor(sql_file)
        preprocessor.process_and_save("schema2.json")
        
    except Exception as e:
        print(f"\n💥 Erreur : {e}")
        raise

if __name__ == "__main__":
    main()
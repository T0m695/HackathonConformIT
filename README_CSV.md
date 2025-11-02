# Export CSV pour AWS RAG

Ce script exporte les données de la base de données SQL vers des fichiers CSV individuels pour une utilisation avec AWS RAG (Retrieval-Augmented Generation).

## Utilisation

```powershell
python export_to_csv.py
```

## Fichiers générés

Le script crée un dossier `csv_exports/` contenant :

### Tables principales
- **corrective_measure.csv** (5,598 lignes) - Mesures correctives
- **event.csv** (2,359 lignes) - Événements de sécurité
- **person.csv** (200 lignes) - Personnes/employés
- **organizational_unit.csv** (25 lignes) - Unités organisationnelles
- **risk.csv** (75 lignes) - Risques identifiés

### Tables de liaison
- **event_corrective_measure.csv** (5,598 lignes) - Liaison événements ↔ mesures
- **event_employee.csv** (5,577 lignes) - Liaison événements ↔ employés
- **event_risk.csv** (6,372 lignes) - Liaison événements ↔ risques

### Vue enrichie
- **measures_enriched.csv** - Vue complète avec jointures (mesures + unités + propriétaires)

## Structure des données

### corrective_measure
- `measure_id` : ID unique de la mesure
- `name` : Nom de la mesure corrective
- `description` : Description détaillée
- `owner_id` : ID du propriétaire/responsable
- `implementation_date` : Date de mise en œuvre
- `cost` : Coût de la mesure
- `organizational_unit_id` : ID de l'unité organisationnelle

### event
- `event_id` : ID unique de l'événement
- `declared_by_id` : ID du déclarant
- `description` : Description de l'événement
- `start_datetime` : Date/heure de début
- `end_datetime` : Date/heure de fin
- `organizational_unit_id` : ID de l'unité concernée
- `type` : Type d'événement (EHS, ENVIRONMENT, DAMAGE)
- `classification` : Classification (INJURY, CHEMICAL_SPILL, etc.)

### person
- `person_id` : ID unique
- `matricule` : Matricule de l'employé
- `name` : Prénom
- `family_name` : Nom de famille
- `role` : Rôle dans l'organisation

### organizational_unit
- `unit_id` : ID unique
- `identifier` : Identifiant de l'unité
- `name` : Nom de l'unité
- `location` : Emplacement

### risk
- `risk_id` : ID unique
- `name` : Nom du risque
- `gravity` : Gravité (LOW, MEDIUM, HIGH, CRITICAL)
- `probability` : Probabilité (VERY_LOW, LOW, MEDIUM, HIGH, VERY_HIGH)

## Utilisation pour AWS RAG

Ces fichiers CSV peuvent être utilisés pour :

1. **Bedrock Knowledge Base** - Charger les données dans Amazon Bedrock
2. **S3 + Athena** - Requêtes SQL sur les données
3. **OpenSearch** - Indexation pour recherche sémantique
4. **SageMaker** - Entraînement de modèles ML

### Exemple d'utilisation avec boto3

```python
import boto3
import pandas as pd

# Charger un fichier CSV
df = pd.read_csv('csv_exports/event.csv')

# Upload vers S3
s3 = boto3.client('s3')
s3.upload_file(
    'csv_exports/event.csv',
    'your-bucket-name',
    'data/event.csv'
)
```

## Notes

- Total : **25,804 lignes** exportées
- Encodage : **UTF-8**
- Séparateur : **virgule (,)**
- Les valeurs NULL sont vides dans les CSV
- Les dates sont au format ISO 8601 (`YYYY-MM-DD HH:MM:SS`)

## Régénération

Pour régénérer les fichiers CSV à partir des données source :
1. Le script lit `data/events.sql`
2. Crée une base SQLite temporaire `events_complete.db`
3. Exporte chaque table vers un CSV individuel
4. Supprime l'ancienne version lors de chaque exécution

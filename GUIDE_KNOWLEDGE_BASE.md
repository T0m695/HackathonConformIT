# Guide de Configuration AWS Bedrock Knowledge Base

## Étapes pour configurer le RAG avec vos fichiers CSV

### 1. Uploader les CSV vers S3

```python
# Créez un script upload_to_s3.py
import boto3
import os

s3 = boto3.client('s3')
bucket_name = 'votre-bucket-name'  # À remplacer

# Upload tous les CSV
for filename in os.listdir('csv_exports'):
    if filename.endswith('.csv'):
        s3.upload_file(
            f'csv_exports/{filename}',
            bucket_name,
            f'rag-data/{filename}'
        )
        print(f"✅ {filename} uploadé")
```

### 2. Créer une Knowledge Base sur AWS

1. **Allez dans AWS Console** → Bedrock → Knowledge Bases
2. **Créez une nouvelle Knowledge Base**
   - Nom: `conformit-events-kb`
   - Description: `Base de connaissances des événements de sécurité`
3. **Configurez la source de données**
   - Type: S3
   - Bucket S3: `votre-bucket-name`
   - Préfixe: `rag-data/`
4. **Choisissez le modèle d'embedding**
   - Recommandé: `Amazon Titan Embeddings G1 - Text`
5. **Créez et synchronisez**
   - Cliquez sur "Create" puis "Sync"
   - Attendez la fin de l'indexation

### 3. Récupérer le Knowledge Base ID

Après création, notez le **Knowledge Base ID** (format: `XXXXXXXXXX`)

### 4. Configurer l'application

Ajoutez le Knowledge Base ID dans votre fichier `.env`:

```bash
KNOWLEDGE_BASE_ID=XXXXXXXXXX
```

### 5. Tester

```python
python main.py
```

Posez une question comme:
- "Quels sont les incidents de déversement chimique?"
- "Liste les mesures correctives pour les risques HIGH"
- "Résume les événements de 2024"

## Fichiers CSV recommandés pour le RAG

Pour de meilleures performances, assurez-vous d'avoir uploadé:

✅ **events_enriched.csv** - Vue complète des événements (PRIORITAIRE)
✅ **measures_enriched.csv** - Mesures correctives avec contexte
✅ **event.csv** - Événements bruts
✅ **corrective_measure.csv** - Toutes les mesures

Les autres fichiers (person, risk, organizational_unit, tables de liaison) peuvent être inclus mais sont moins critiques pour le RAG car leurs données sont déjà dans les vues enrichies.

## Dépannage

### Erreur "Knowledge Base not found"
- Vérifiez que le KNOWLEDGE_BASE_ID est correct
- Assurez-vous que la Knowledge Base est dans la même région que vos credentials AWS

### Erreur "Access Denied"
- Vérifiez que votre utilisateur IAM a les permissions:
  - `bedrock:Retrieve`
  - `bedrock:InvokeModel`
  - `s3:GetObject` sur le bucket

### Aucun résultat trouvé
- Attendez que la synchronisation soit complète
- Vérifiez que les fichiers CSV sont bien dans S3
- Relancez une synchronisation manuelle

## Architecture du RAG

```
User Query
    ↓
retrieve_from_knowledge_base()  ← Recherche sémantique dans les embeddings
    ↓
Top 5 documents pertinents
    ↓
search_events()  ← Génère la réponse avec Claude + contexte
    ↓
Réponse avec sources
```

## Coûts estimés

- **Embeddings Titan**: ~$0.0001 par 1000 tokens
- **Stockage S3**: ~$0.023 par GB/mois
- **Claude 3 Haiku**: ~$0.00025 par 1000 tokens input
- **Coût estimé pour 10 fichiers CSV**: ~$1-2/mois

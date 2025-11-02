# 🤖 Fonction d'Analyse SQL avec AWS Bedrock

## 📋 Description

La fonction `query_with_ai()` permet d'analyser des résultats de requêtes SQL en utilisant l'intelligence artificielle d'AWS Bedrock (Claude 3 Haiku).

## 🚀 Installation

```bash
pip install boto3 python-dotenv psycopg2-binary
```

## ⚙️ Configuration

Assurez-vous que votre fichier `.env` contient les credentials AWS :

```env
AWS_ACCESS_KEY_ID=votre_access_key
AWS_SECRET_ACCESS_KEY=votre_secret_key
AWS_SESSION_TOKEN=votre_session_token
AWS_DEFAULT_REGION=us-east-1
```

## 📖 Utilisation de base

### Import

```python
from ai_query import query_with_ai
```

### Exemple simple

```python
# Résultats SQL (liste de dictionnaires)
sql_results = [
    {"id": 1, "titre": "Incident chimique", "date": "2024-01-15", "gravite": "HIGH"},
    {"id": 2, "titre": "Chute", "date": "2024-02-20", "gravite": "LOW"}
]

# Prompt utilisateur
prompt = "Résume les incidents par gravité"

# Obtenir la réponse IA
reponse = query_with_ai(sql_results, prompt)
print(reponse)
```

## 🔗 Intégration avec PostgreSQL

```python
import psycopg2.extras
from ai_query import query_with_ai

# Connexion PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    database="hackathon",
    user="postgres",
    password="admin"
)

# Exécuter une requête
cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cursor.execute("SELECT * FROM corrective_measure LIMIT 10")
results = [dict(row) for row in cursor.fetchall()]

# Analyser avec l'IA
reponse = query_with_ai(results, "Quelles sont les mesures les plus importantes?")
print(reponse)
```

## 💡 Exemples de prompts

### 1. Analyse statistique
```python
prompt = "Combien d'incidents par catégorie? Quelle est la tendance?"
```

### 2. Recommandations
```python
prompt = "Quelles mesures correctives recommandes-tu pour réduire les incidents?"
```

### 3. Comparaison
```python
prompt = "Compare les performances de sécurité entre les différentes unités"
```

### 4. Prédiction
```python
prompt = "En te basant sur ces données, quels sont les risques futurs?"
```

## 📊 Fonction détaillée

### Signature

```python
def query_with_ai(sql_results: List[Dict[str, Any]], user_prompt: str) -> str
```

### Paramètres

- **sql_results** (List[Dict]): Résultats de la requête SQL sous forme de liste de dictionnaires
- **user_prompt** (str): Question ou instruction de l'utilisateur

### Retour

- **str**: Réponse générée par l'IA avec métadonnées

### Exemple complet

```python
from ai_query import query_with_ai

# Données
data = [
    {
        "measure_id": 1,
        "name": "Formation sécurité",
        "date": "2024-01-15",
        "unit": "Production"
    },
    {
        "measure_id": 2,
        "name": "Audit équipements",
        "date": "2024-02-01",
        "unit": "Maintenance"
    }
]

# Différents types de questions
questions = [
    "Résume ces mesures correctives",
    "Quelle unité est la plus proactive?",
    "Recommande des améliorations",
    "Calcule le délai moyen entre les mesures"
]

for q in questions:
    print(f"\n❓ Question: {q}")
    print(query_with_ai(data, q))
    print("-" * 80)
```

## 🎯 Cas d'usage

### 1. Dashboard interactif
```python
# L'utilisateur pose une question via l'interface web
user_question = request.json['question']

# Récupérer les données pertinentes
sql = "SELECT * FROM events WHERE date > '2024-01-01'"
results = execute_query(sql)

# Générer la réponse IA
answer = query_with_ai(results, user_question)

# Retourner au frontend
return jsonify({"answer": answer})
```

### 2. Rapport automatique
```python
# Générer un rapport hebdomadaire
weekly_data = get_weekly_incidents()

report = query_with_ai(
    weekly_data,
    "Crée un résumé exécutif des incidents de cette semaine avec recommandations"
)

send_email(to="manager@company.com", body=report)
```

### 3. Chatbot intelligent
```python
# Bot qui répond aux questions sur les données
while True:
    user_input = input("Votre question: ")
    
    # Rechercher les données pertinentes
    data = search_relevant_data(user_input)
    
    # Générer la réponse
    response = query_with_ai(data, user_input)
    
    print(f"\n🤖 {response}\n")
```

## ⚠️ Limitations

- **Tokens**: Maximum ~100 résultats SQL pour éviter de dépasser la limite de tokens
- **Coût**: Chaque appel coûte ~$0.00025 (Claude 3 Haiku)
- **Latence**: 1-3 secondes par requête
- **Rate limit**: Respecter les limites AWS (dépend de votre compte)

## 🔧 Gestion des erreurs

La fonction gère automatiquement ces erreurs :

- ❌ Credentials AWS manquants
- 🔑 Token AWS expiré
- 🚫 Permissions insuffisantes
- ⏱️ Rate limiting
- 📡 Erreurs réseau

## 🧪 Tests

Tester la fonction :

```bash
# Test avec données simulées
python ai_query.py

# Test avec PostgreSQL
python exemple_usage.py
```

## 📚 Documentation AWS

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Claude 3 API Reference](https://docs.anthropic.com/claude/reference)
- [Pricing Claude 3 Haiku](https://aws.amazon.com/bedrock/pricing/)

## 🤝 Support

Pour toute question sur l'utilisation de cette fonction, consultez les exemples dans `exemple_usage.py`.

---

**✨ Développé avec AWS Bedrock et Claude 3 Haiku**

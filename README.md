# TechnoPlast Safety Dashboard

Dashboard web interactif avec chatbot IA pour l'analyse des événements de sécurité.

## 🚀 Démarrage rapide

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer le serveur web
python app.py
```

Accédez à http://localhost:8000

## ✨ Fonctionnalités

- 📊 **Métriques en temps réel** : Visualisation des événements et catégories
- 💬 **Chatbot IA** : Assistant intelligent pour rechercher des événements
- 📈 **Graphiques interactifs** : Distribution par catégorie et tendances mensuelles
- 🔄 **Mise à jour automatique** : Rafraîchissement toutes les 30 secondes

## 🏗️ Architecture

- **Backend** : FastAPI + PostgreSQL
- **Frontend** : HTML/CSS/JavaScript + Chart.js
- **IA** : AWS Bedrock (Claude 3 Haiku)

## 🐳 Docker

```bash
docker build -t technoplast-dashboard .
docker run -p 8000:8000 --env-file .env technoplast-dashboard
```

## 🔧 Dépannage

### Problème: Aucune donnée n'apparaît

1. **Vérifier la connexion PostgreSQL**:
   ```bash
   psql -h localhost -U postgres -d hackathon
   ```

2. **Vérifier que la table existe**:
   ```sql
   \c hackathon
   SELECT COUNT(*) FROM corrective_measure;
   ```

3. **Vérifier les credentials**:
   - Host: localhost
   - Database: hackathon
   - User: postgres
   - Password: admin
   - Port: 5432

4. **Réinstaller les dépendances**:
   ```bash
   pip install -r requirements.txt
   ```

### Problème: Erreur de connexion PostgreSQL

- Vérifiez que PostgreSQL est démarré
- Vérifiez que la base de données 'hackathon' existe
- Vérifiez le mot de passe (admin)
- Vérifiez que le port 5432 est accessible
- Créez la base si elle n'existe pas: `CREATE DATABASE hackathon;`

### Problème: Erreur AWS Bedrock

- Renouvelez vos credentials: `aws sts get-session-token`
- Vérifiez la région dans `.env`: `AWS_DEFAULT_REGION=us-east-1`
- Vérifiez l'accès à Bedrock dans la console AWS

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

- **Backend** : FastAPI + SQLite
- **Frontend** : HTML/CSS/JavaScript + Chart.js
- **IA** : AWS Bedrock (Claude 3 Haiku)

## 🐳 Docker

```bash
docker build -t technoplast-dashboard .
docker run -p 8000:8000 --env-file .env technoplast-dashboard
```

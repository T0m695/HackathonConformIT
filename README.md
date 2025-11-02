# TechnoPlast Safety Dashboard

Dashboard web interactif avec chatbot IA pour l'analyse des événements de sécurité.

## 🚀 Démarrage rapide

### Exécution locale

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer le serveur web
python app.py
```

Accédez à http://localhost:8000

### Exécution avec Docker

#### Option 1 : Docker Compose (Recommandé)

```bash
# Placer le fichier de backup à ./sql/event-bis.backup

# Copier le fichier .env.example vers .env et le configurer
cp .env.example .env

# Lancer avec Docker Compose
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Arrêter
docker-compose down
```

#### Option 2 : Docker seul

```bash
# Build l'image
docker build -t technoplast-dashboard .

# Run le conteneur (Windows)
docker run -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=5432 \
  -e DB_NAME=hackathon \
  -e DB_USER=postgres \
  -e DB_PASSWORD=admin \
  --env-file .env \
  technoplast-dashboard

# Run le conteneur (Linux/Mac)
docker run -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=5432 \
  -e DB_NAME=hackathon \
  -e DB_USER=postgres \
  -e DB_PASSWORD=admin \
  --env-file .env \
  technoplast-dashboard
```

## 🔧 Configuration de la base de données pour Docker

### Windows

PostgreSQL doit être configuré pour accepter les connexions externes :

1. **Modifier `postgresql.conf`** (généralement dans `C:\Program Files\PostgreSQL\XX\data\`) :
   ```
   listen_addresses = '*'
   ```

2. **Modifier `pg_hba.conf`** pour autoriser les connexions depuis Docker :
   ```
   # IPv4 local connections:
   host    all             all             172.17.0.0/16           md5
   host    all             all             127.0.0.1/32            md5
   ```

3. **Redémarrer PostgreSQL** :
   ```powershell
   # PowerShell en tant qu'administrateur
   Restart-Service postgresql-x64-XX
   ```

### Linux/Mac

Si PostgreSQL tourne sur l'hôte, assurez-vous qu'il écoute sur toutes les interfaces :

```bash
# Éditer postgresql.conf
sudo nano /etc/postgresql/XX/main/postgresql.conf
# Définir: listen_addresses = '*'

# Éditer pg_hba.conf
sudo nano /etc/postgresql/XX/main/pg_hba.conf
# Ajouter: host all all 172.17.0.0/16 md5

# Redémarrer PostgreSQL
sudo systemctl restart postgresql
```

## 🐛 Dépannage Docker

### Le conteneur ne peut pas se connecter à PostgreSQL

1. **Vérifier que PostgreSQL écoute sur le bon port** :
   ```bash
   # Windows
   netstat -an | findstr 5432
   
   # Linux/Mac
   netstat -an | grep 5432
   ```

2. **Tester la connexion depuis le conteneur** :
   ```bash
   docker exec -it <container_id> bash
   psql -h host.docker.internal -U postgres -d hackathon
   ```

3. **Vérifier les logs Docker** :
   ```bash
   docker logs <container_id>
   ```

4. **Vérifier le pare-feu Windows** :
   - Ouvrir le port 5432 pour PostgreSQL
   - Autoriser les connexions entrantes

### Erreur "host.docker.internal" non résolu

Sur Linux, utilisez :
```bash
docker run --add-host=host.docker.internal:host-gateway ...
```

Ou dans docker-compose.yml :
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## ✨ Fonctionnalités

- 📊 **Métriques en temps réel** : Visualisation des événements et catégories
- 💬 **Chatbot IA** : Assistant intelligent pour rechercher des événements
- 📈 **Graphiques interactifs** : Distribution par catégorie et tendances mensuelles
- 🔄 **Mise à jour automatique** : Rafraîchissement toutes les 30 secondes

## 🏗️ Architecture

- **Backend** : FastAPI + PostgreSQL
- **Frontend** : HTML/CSS/JavaScript + Chart.js
- **IA** : AWS Bedrock (Claude 3 Haiku)
- **Données** : Événements de sécurité avec mesures correctives associées

## 📊 Structure des données

Le système charge les événements (`event`) avec leurs mesures correctives (`corrective_measure`) associées via la table de liaison `event_corrective_measure`.

Le fichier de backup PostgreSQL se trouve à `./sql/event-bis.backup`.

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

2. **Vérifier que les tables existent**:
   ```sql
   \c hackathon
   SELECT COUNT(*) FROM event;
   SELECT COUNT(*) FROM corrective_measure;
   SELECT COUNT(*) FROM event_corrective_measure;
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

# Guide Docker pour HackathonConformIT

## Prérequis
- Docker Desktop installé et démarré
- WSL2 activé (Windows)
- Credentials AWS configurés

## Configuration

1. **Démarrer Docker Desktop** en mode administrateur
2. Créer un fichier `.env` avec vos credentials AWS :
```
AWS_ACCESS_KEY_ID=votre_access_key
AWS_SECRET_ACCESS_KEY=votre_secret_key
AWS_SESSION_TOKEN=votre_session_token
AWS_DEFAULT_REGION=us-east-1
```

## Démarrage

### Option 1: Docker Compose (recommandé)
```powershell
# Dans PowerShell en mode administrateur
# Construire et démarrer le conteneur
docker-compose up --build

# Démarrer en arrière-plan
docker-compose up -d --build
```

### Option 2: Docker direct
```powershell
# Construire l'image
docker build -t hackathon-conformit .

# Démarrer le conteneur (Windows)
docker run -it --rm --env-file .env -v ${PWD}/data:/app/data hackathon-conformit
```

## Commandes utiles

```powershell
# Voir les logs
docker-compose logs -f

# Arrêter le conteneur
docker-compose down

# Redémarrer
docker-compose restart

# Accéder au shell du conteneur
docker-compose exec hackathon-app /bin/bash
```

## Dépannage Windows

### Docker Desktop n'est pas démarré
```powershell
# Vérifier que Docker Desktop est en cours d'exécution
docker version
```

### Problèmes de permissions
```powershell
# Exécuter PowerShell en mode administrateur
# Ou utiliser WSL2
wsl
cd /mnt/c/Fichiers/UQAC/Hackathon/HackathonConformIT
docker-compose up --build
```

### Problème de connexion Docker
1. Redémarrer Docker Desktop
2. Vérifier que WSL2 est activé
3. Exécuter en mode administrateur

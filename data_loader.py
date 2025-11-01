from database import load_events as db_load_events
from typing import List, Dict

def load_events(filepath: str = "data/events.sql") -> List[Dict]:
    """Charge les événements depuis la base de données SQLite."""
    # Utilise la fonction de database.py au lieu d'essayer de lire un JSON
    return db_load_events()

def format_event(event: Dict) -> str:
    """Formate un événement pour l'affichage."""
    return f"""
Titre: {event.get('titre', 'N/A')}
Date: {event.get('date', 'N/A')}
Lieu: {event.get('lieu', 'N/A')}
Description: {event.get('description', 'N/A')}
Catégorie: {event.get('categorie', 'N/A')}
"""

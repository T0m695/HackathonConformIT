"""
Module pour créer de nouveaux événements dans la table event
"""
import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import Optional, Dict, List
from database import get_connection


def create_event(
    declared_by_id: int,
    description: str,
    start_datetime: datetime,
    organizational_unit_id: int,
    event_type: str,
    classification: str,
    end_datetime: Optional[datetime] = None
) -> Dict:
    """
    Crée un nouvel événement dans la base de données.
    
    Args:
        declared_by_id: ID de la personne qui déclare l'événement (clé étrangère vers person)
        description: Description détaillée de l'événement
        start_datetime: Date et heure de début de l'événement
        organizational_unit_id: ID de l'unité organisationnelle (clé étrangère vers organizational_unit)
        event_type: Type d'événement - doit être 'EHS', 'ENVIRONMENT', ou 'DAMAGE'
        classification: Classification de l'événement - doit être l'une des valeurs:
            'INJURY', 'FIRST_AID', 'LOST_TIME', 'PREVENTIVE_DECLARATION', 
            'FIRE', 'FIRE_ALARM', 'AUDIT', 'CHEMICAL_SPILL', 
            'EQUIPMENT_FAILURE', 'NEAR_MISS', 'PROPERTY_DAMAGE', 
            'ENVIRONMENTAL_INCIDENT', 'GRAVITY'
        end_datetime: Date et heure de fin de l'événement (optionnel)
    
    Returns:
        Dict contenant les informations de l'événement créé avec son event_id
    
    Raises:
        ValueError: Si les paramètres ne sont pas valides
        psycopg2.Error: Si une erreur de base de données survient
    """
    
    # Validation des types d'événements
    valid_types = ['EHS', 'ENVIRONMENT', 'DAMAGE']
    if event_type not in valid_types:
        raise ValueError(f"Type d'événement invalide. Doit être l'un de: {valid_types}")
    
    # Validation des classifications
    valid_classifications = [
        'INJURY', 'FIRST_AID', 'LOST_TIME', 'PREVENTIVE_DECLARATION',
        'FIRE', 'FIRE_ALARM', 'AUDIT', 'CHEMICAL_SPILL',
        'EQUIPMENT_FAILURE', 'NEAR_MISS', 'PROPERTY_DAMAGE',
        'ENVIRONMENTAL_INCIDENT', 'GRAVITY'
    ]
    if classification not in valid_classifications:
        raise ValueError(f"Classification invalide. Doit être l'une de: {valid_classifications}")
    
    # Validation de la description
    if not description or len(description.strip()) < 10:
        raise ValueError("La description doit contenir au moins 10 caractères")
    
    # Validation des dates
    if end_datetime and end_datetime < start_datetime:
        raise ValueError("La date de fin doit être postérieure à la date de début")
    
    print(f"\n🔍 DEBUG - Création d'événement:")
    print(f"   declared_by_id: {declared_by_id}")
    print(f"   description: {description[:100]}{'...' if len(description) > 100 else ''}")
    print(f"   organizational_unit_id: {organizational_unit_id}")
    print(f"   event_type: {event_type}")
    print(f"   classification: {classification}")
    
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Insérer le nouvel événement
        insert_query = """
            INSERT INTO event (
                declared_by_id,
                description,
                start_datetime,
                end_datetime,
                organizational_unit_id,
                type,
                classification
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING event_id, declared_by_id, description, start_datetime, 
                      end_datetime, organizational_unit_id, type, classification
        """
        
        cursor.execute(
            insert_query,
            (
                declared_by_id,
                description,
                start_datetime,
                end_datetime,
                organizational_unit_id,
                event_type,
                classification
            )
        )
        
        # Récupérer l'événement créé
        created_event = cursor.fetchone()
        conn.commit()
        
        print(f"✅ Événement créé avec succès - ID: {created_event['event_id']}")
        
        cursor.close()
        conn.close()
        
        # Convertir en dict Python standard
        return dict(created_event)
        
    except psycopg2.IntegrityError as e:
        print(f"❌ Erreur d'intégrité: {e}")
        raise ValueError(f"Erreur d'intégrité de la base de données: {str(e)}")
    except psycopg2.Error as e:
        print(f"❌ Erreur PostgreSQL: {e}")
        raise
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        raise


def create_event_with_corrective_measures(
    declared_by_id: int,
    description: str,
    start_datetime: datetime,
    organizational_unit_id: int,
    event_type: str,
    classification: str,
    measure_ids: List[int],
    end_datetime: Optional[datetime] = None
) -> Dict:
    """
    Crée un nouvel événement avec des mesures correctives associées.
    
    Args:
        (mêmes arguments que create_event)
        measure_ids: Liste des IDs de mesures correctives à associer à l'événement
    
    Returns:
        Dict contenant les informations de l'événement créé avec ses mesures correctives
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Créer l'événement
        event = create_event(
            declared_by_id=declared_by_id,
            description=description,
            start_datetime=start_datetime,
            organizational_unit_id=organizational_unit_id,
            event_type=event_type,
            classification=classification,
            end_datetime=end_datetime
        )
        
        event_id = event['event_id']
        
        # Associer les mesures correctives
        if measure_ids:
            for measure_id in measure_ids:
                cursor.execute(
                    """
                    INSERT INTO event_corrective_measure (event_id, measure_id)
                    VALUES (%s, %s)
                    """,
                    (event_id, measure_id)
                )
            
            conn.commit()
            print(f"✅ {len(measure_ids)} mesure(s) corrective(s) associée(s) à l'événement {event_id}")
        
        # Récupérer l'événement complet avec les mesures correctives
        cursor.execute(
            """
            SELECT 
                e.*,
                (
                    SELECT json_agg(
                        json_build_object(
                            'measure_id', cm.measure_id,
                            'name', cm.name,
                            'description', cm.description,
                            'implementation_date', cm.implementation_date,
                            'cost', cm.cost
                        )
                    )
                    FROM event_corrective_measure ecm
                    JOIN corrective_measure cm ON ecm.measure_id = cm.measure_id
                    WHERE ecm.event_id = e.event_id
                ) as corrective_measures
            FROM event e
            WHERE e.event_id = %s
            """,
            (event_id,)
        )
        
        complete_event = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return dict(complete_event)
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'événement avec mesures: {e}")
        if conn:
            conn.rollback()
        raise


# Exemple d'utilisation
if __name__ == "__main__":
    from datetime import datetime, timedelta
    
    # Exemple 1: Créer un événement simple
    try:
        new_event = create_event(
            declared_by_id=1,  # ID d'une personne existante dans la table person
            description="Test d'incident mineur dans l'atelier de production",
            start_datetime=datetime.now(),
            organizational_unit_id=1,  # ID d'une unité organisationnelle existante
            event_type="EHS",
            classification="NEAR_MISS"
        )
        
        print("\n📝 Événement créé:")
        print(f"   ID: {new_event['event_id']}")
        print(f"   Type: {new_event['type']}")
        print(f"   Classification: {new_event['classification']}")
        print(f"   Description: {new_event['description']}")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
    
    # Exemple 2: Créer un événement avec mesures correctives
    try:
        new_event_with_measures = create_event_with_corrective_measures(
            declared_by_id=1,
            description="Incident avec mesures correctives",
            start_datetime=datetime.now(),
            organizational_unit_id=1,
            event_type="EHS",
            classification="EQUIPMENT_FAILURE",
            measure_ids=[1, 2],  # IDs de mesures correctives existantes
            end_datetime=datetime.now() + timedelta(hours=2)
        )
        
        print("\n📝 Événement avec mesures créé:")
        print(f"   ID: {new_event_with_measures['event_id']}")
        print(f"   Mesures correctives: {len(new_event_with_measures.get('corrective_measures', []))}")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")


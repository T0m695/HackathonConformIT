from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import psycopg2
import psycopg2.extras
import json
from database import get_connection, init_database
from typing import Dict, List
import os
from datetime import datetime
from ATTEMPT1.pipeline import EnhancedRAGPipeline
from ATTEMPT1.config import logger

app = FastAPI(title="TechnoPlast Safety Dashboard")

# Initialize RAG pipeline
try:
    rag_pipeline = EnhancedRAGPipeline()
    print("✅ Agent IA initialisé avec succès")
except Exception as e:
    logger.error(f"⚠️ Erreur initialisation agent: {e}")
    rag_pipeline = None

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    timestamp: str

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the dashboard homepage."""
    with open("templates/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle chat requests from the frontend."""
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="Agent IA non disponible")
    
    try:
        result = rag_pipeline.ask(request.message)
        # The result will be a dict with SQL and results
        if not result.get('success'):
            response = f"Erreur: {result.get('error', 'Une erreur est survenue')}"
        else:
            # Format the response with SQL and results
            sql = result.get('sql', 'Aucune requête SQL générée')
            sql_result = result.get('result', 'Aucun résultat trouvé')
            response = f"SQL généré:\n{sql}\n\nRésultats:\n"
            if isinstance(sql_result, (list, dict)):
                response += json.dumps(sql_result, ensure_ascii=False, indent=2)
            else:
                response += str(sql_result)
        
        return ChatResponse(
            response=str(response),
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/event/{event_id}", response_class=HTMLResponse)
async def event_detail_page(event_id: int):
    """Serve the event detail page."""
    with open("templates/event-detail.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/event/{event_id}")
async def get_event_details(event_id: int):
    """Get detailed information about a specific event."""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get event details with corrective measures
        cursor.execute("""
            SELECT 
                e.event_id as id,
                COALESCE(e.classification, 'Classification inconnue') as titre,
                COALESCE(e.description, 'Description non disponible') as description,
                COALESCE(TO_CHAR(e.start_datetime, 'YYYY-MM-DD'), '2024-01-01') as date,
                CASE 
                    WHEN e.end_datetime IS NULL THEN 'En cours'
                    ELSE 'Résolu le ' || TO_CHAR(e.end_datetime, 'YYYY-MM-DD')
                END as statut,
                e.end_datetime IS NULL as en_cours,
                e.type as categorie,
                COALESCE(ou.location, 'Non spécifié') as lieu,
                COALESCE(p.name || ' ' || p.family_name, 'Non spécifié') as personne,
                COALESCE(r.name, 'Non spécifié') as risque,
                COALESCE(r.gravity, 'Non spécifié') as gravite,
                COALESCE(r.probability, 'Non spécifié') as probabilite,
                (
                    SELECT json_agg(
                        json_build_object(
                            'measure_id', cm.measure_id,
                            'name', cm.name,
                            'description', cm.description,
                            'implementation_date', TO_CHAR(cm.implementation_date, 'YYYY-MM-DD'),
                            'cost', cm.cost::text
                        )
                    )
                    FROM event_corrective_measure ecm
                    JOIN corrective_measure cm ON ecm.measure_id = cm.measure_id
                    WHERE ecm.event_id = e.event_id
                ) as mesures_correctives
            FROM event e
            LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
            LEFT JOIN person p ON e.declared_by_id = p.person_id
            LEFT JOIN event_risk ON e.event_id = event_risk.event_id
            LEFT JOIN risk r ON event_risk.risk_id = r.risk_id
            WHERE e.event_id = %s
        """, (event_id,))
        
        event = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        
        # Convert to dict and handle null mesures_correctives
        event_dict = dict(event)
        if not event_dict.get('mesures_correctives'):
            event_dict['mesures_correctives'] = []
            
        return event_dict
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics")
async def get_metrics(duration: int = 12):
    """Get database metrics for the dashboard."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM event")
        total_events = cursor.fetchone()[0]
        
        # Events by location
        cursor.execute("""
            SELECT 
                COALESCE(ou.location, 'Non spécifié') as location_name,
                COUNT(*) as count
            FROM event e
            LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
            GROUP BY ou.location
            ORDER BY count DESC
            LIMIT 10
        """)
        categories = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        # Recent events avec mesures correctives
        cursor.execute("""
            SELECT 
                e.event_id as id,
                COALESCE(e.classification, 'Classification inconnue') as titre,
                COALESCE(TO_CHAR(e.start_datetime, 'YYYY-MM-DD'), '2024-01-01') as date,
                COALESCE(ou.location, 'Non spécifié') as lieu,
                e.type as categorie,
                (
                    SELECT COUNT(*)
                    FROM event_corrective_measure ecm
                    WHERE ecm.event_id = e.event_id
                ) as nb_mesures
            FROM event e
            LEFT JOIN organizational_unit ou ON e.organizational_unit_id = ou.unit_id
            ORDER BY e.start_datetime DESC 
            LIMIT 10
        """)
        
        recent_events = []
        for row in cursor.fetchall():
            recent_events.append({
                "id": row[0],
                "titre": row[1],
                "date": row[2],
                "lieu": row[3],
                "categorie": row[4],
                "nb_mesures": row[5]
            })
        
        # Events by month avec durée paramétrable - gérer le cas "Tous"
        if duration >= 999:
            # Pour "Tous", récupérer tous les événements sans filtre de date
            cursor.execute("""
                SELECT 
                    TO_CHAR(e.start_datetime, 'YYYY-MM') as month,
                    COUNT(*) as count
                FROM event e
                WHERE e.start_datetime IS NOT NULL
                GROUP BY TO_CHAR(e.start_datetime, 'YYYY-MM')
                ORDER BY month DESC
            """)
        else:
            # Pour une durée spécifique, générer tous les mois
            cursor.execute("""
                WITH months AS (
                    SELECT TO_CHAR(
                        CURRENT_DATE - INTERVAL '1 month' * generate_series(0, %s - 1),
                        'YYYY-MM'
                    ) as month
                )
                SELECT 
                    m.month,
                    COALESCE(COUNT(e.event_id), 0) as count
                FROM months m
                LEFT JOIN event e
                    ON TO_CHAR(e.start_datetime, 'YYYY-MM') = m.month
                GROUP BY m.month
                ORDER BY m.month DESC
            """, (duration,))
        
        monthly_stats = [{"month": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return {
            "total_events": total_events,
            "categories": categories,
            "recent_events": recent_events,
            "monthly_stats": monthly_stats,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def healthcheck():
    """Check application health status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database_connected": True,
        "agent_available": rag_pipeline is not None,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    print("🚀 Démarrage du serveur web sur http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

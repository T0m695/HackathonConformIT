from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import psycopg2
import psycopg2.extras
from agent import EventAgent
from database import get_connection, init_database
from typing import Dict, List
import os
from datetime import datetime

app = FastAPI(title="TechnoPlast Safety Dashboard")

# Initialize agent
try:
    agent = EventAgent()
    print("✅ Agent IA initialisé avec succès")
except Exception as e:
    print(f"⚠️ Erreur initialisation agent: {e}")
    agent = None

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
    if not agent:
        raise HTTPException(status_code=503, detail="Agent IA non disponible")
    
    try:
        response = agent.search_events(request.message)
        return ChatResponse(
            response=response,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
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
                e.event_id,
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
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_available": agent is not None,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    print("🚀 Démarrage du serveur web sur http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

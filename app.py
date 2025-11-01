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
async def get_metrics():
    """Get database metrics for the dashboard."""
    try:
        print("🔍 DEBUG: Début de get_metrics()")
        conn = get_connection()
        cursor = conn.cursor()
        
        # Essayer d'interroger directement la table
        try:
            cursor.execute("SELECT COUNT(*) FROM corrective_measure")
            total_events = cursor.fetchone()[0]
            print(f"✅ Total événements: {total_events}")
        except psycopg2.Error as e:
            print(f"❌ Erreur lors de la requête corrective_measure: {e}")
            raise HTTPException(status_code=500, detail=f"Impossible d'accéder à la table corrective_measure: {str(e)}")
        
        # Events by organizational unit
        cursor.execute("""
            SELECT 
                COALESCE(CAST(organizational_unit_id AS VARCHAR), 'Non spécifié') as unit_name,
                COUNT(*) as count 
            FROM corrective_measure 
            GROUP BY organizational_unit_id
            ORDER BY count DESC
            LIMIT 10
        """)
        categories = [{"name": f"Unité {row[0]}", "count": row[1]} for row in cursor.fetchall()]
        print(f"✅ Catégories: {len(categories)}")
        
        # Recent events
        cursor.execute("""
            SELECT 
                measure_id,
                COALESCE(name, 'Mesure corrective') as titre,
                COALESCE(TO_CHAR(implementation_date, 'YYYY-MM-DD'), '2024-01-01') as date,
                CONCAT('Unité ', COALESCE(CAST(organizational_unit_id AS VARCHAR), 'N/A')) as lieu,
                'Mesure corrective' as categorie
            FROM corrective_measure 
            ORDER BY measure_id DESC 
            LIMIT 10
        """)
        
        recent_events = []
        for row in cursor.fetchall():
            recent_events.append({
                "titre": row[1] if len(row) > 1 else f"Mesure #{row[0]}",
                "date": row[2] if len(row) > 2 else "2024-01-01",
                "lieu": row[3] if len(row) > 3 else "Non spécifié",
                "categorie": row[4] if len(row) > 4 else "Mesure corrective"
            })
        
        print(f"✅ Événements récents: {len(recent_events)}")
        
        # Events by month
        cursor.execute("""
            SELECT 
                TO_CHAR(implementation_date, 'YYYY-MM') as month,
                COUNT(*) as count
            FROM corrective_measure
            WHERE implementation_date IS NOT NULL
            GROUP BY TO_CHAR(implementation_date, 'YYYY-MM')
            ORDER BY month DESC
            LIMIT 12
        """)
        monthly_stats = [{"month": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        print(f"✅ Statistiques mensuelles: {len(monthly_stats)}")
        
        cursor.close()
        conn.close()
        
        result = {
            "total_events": total_events,
            "categories": categories,
            "recent_events": recent_events,
            "monthly_stats": monthly_stats,
            "timestamp": datetime.now().isoformat()
        }
        
        print("✅ get_metrics() terminé avec succès")
        return result
        
    except psycopg2.Error as e:
        error_msg = f"Erreur PostgreSQL: {e.pgerror if hasattr(e, 'pgerror') else str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Erreur base de données: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

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

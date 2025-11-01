from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
from agent import EventAgent
from database import get_connection
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
        conn = get_connection()
        cursor = conn.cursor()
        
        # Total events
        cursor.execute("SELECT COUNT(*) FROM events")
        total_events = cursor.fetchone()[0]
        
        # Events by category
        cursor.execute("""
            SELECT categorie, COUNT(*) as count 
            FROM events 
            GROUP BY categorie
            ORDER BY count DESC
        """)
        categories = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        # Recent events (last 10)
        cursor.execute("""
            SELECT titre, date, lieu, categorie 
            FROM events 
            ORDER BY date DESC 
            LIMIT 10
        """)
        recent_events = [
            {
                "titre": row[0],
                "date": row[1],
                "lieu": row[2],
                "categorie": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        # Events by month (if dates are parseable)
        cursor.execute("""
            SELECT 
                strftime('%Y-%m', date) as month,
                COUNT(*) as count
            FROM events
            WHERE date IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """)
        monthly_stats = [{"month": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "total_events": total_events,
            "categories": categories,
            "recent_events": recent_events,
            "monthly_stats": monthly_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur base de données: {str(e)}")

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

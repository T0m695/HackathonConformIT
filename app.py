from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn
import psycopg2
import psycopg2.extras
from psycopg2 import errors as psycopg2_errors
from visualization_agent import VisualizationAgent
import json
from database import get_connection, init_database
from typing import Dict, List
import os
from datetime import datetime
from ATTEMPT1.pipeline import EnhancedRAGPipeline
from ATTEMPT1.config import logger
from bardin import query_with_ai
import boto3
import uuid
import time
import requests
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import cm
from reportlab.lib import colors
import base64

load_dotenv()

app = FastAPI(title="TechnoPlast Safety Dashboard")

# Initialize agents
# Initialize RAG pipeline
try:
    rag_pipeline = EnhancedRAGPipeline()
    print("✅ Agent IA initialisé avec succès")
except Exception as e:
    logger.error(f"⚠️ Erreur initialisation agent: {e}")
    rag_pipeline = None



try:
    viz_agent = VisualizationAgent()
    print("✅ Agent de visualisation initialisé avec succès")
except Exception as e:
    print(f"⚠️ Erreur initialisation agent visualisation: {e}")
    viz_agent = None

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
            sql_result = result.get('result', 'Aucun résultat trouvé')
            # Utiliser bardin.py pour générer une réponse intelligente avec l'IA
            response = query_with_ai(sql_result, request.message)

        return ChatResponse(
            response=str(response),
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/visualize")
async def visualize(request: ChatRequest):
    """Handle visualization requests from the frontend."""
    if not viz_agent:
        raise HTTPException(status_code=503, detail="Agent de visualisation non disponible")
    
    try:
        result = viz_agent.process_query(request.message)
        return {
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ Erreur visualisation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/event/{event_id}", response_class=HTMLResponse)
async def event_detail_page(event_id: int):
    """Serve the event detail page."""
    with open("templates/event-detail.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/ask", response_class=HTMLResponse)
async def ask_question_page():
    """Serve the ask question page."""
    with open("templates/ask-question.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/deposer-alerte", response_class=HTMLResponse)
async def deposer_alerte_page():
    """Serve the alert submission page."""
    with open("templates/deposer-alerte.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/analyser-image", response_class=HTMLResponse)
async def analyser_image_page():
    """Serve the image analysis page."""
    with open("templates/analyser-image.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/analyze-image")
async def analyze_image(image: UploadFile = File(...)):
    """Analyze an image for safety risks using AWS Bedrock and return a PDF report."""
    try:
        logger.info(f"📸 Réception d'une image: {image.filename}")
        
        # Validate file type
        if not image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Le fichier doit être une image")
        
        # Read image
        image_bytes = await image.read()
        
        # Validate image size (10 MB max)
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="L'image est trop volumineuse (max 10 MB)")
        
        logger.info(f"✅ Image chargée: {len(image_bytes)} octets")
        
        # Encode image to base64 for Bedrock
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Determine image format
        image_format = "jpeg"
        if image.content_type == "image/png":
            image_format = "png"
        elif image.content_type == "image/webp":
            image_format = "webp"
        
        # Call AWS Bedrock for analysis
        logger.info("🤖 Appel à AWS Bedrock pour l'analyse...")
        bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name='us-east-1'
        )
        
        prompt = """Vous êtes un expert en sécurité industrielle et en analyse d'images. Analysez cette image et identifiez tous les risques de sécurité présents.

Pour chaque risque identifié, fournissez :
1. Le type de risque (chute, électricité, produits chimiques, équipement, etc.)
2. La gravité (Faible/Moyenne/Élevée/Critique)
3. Une description détaillée du risque
4. Des recommandations précises pour corriger le problème

Structurez votre réponse de manière claire avec des titres et des listes à puces.
Soyez exhaustif et détaillé dans votre analyse."""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": f"image/{image_format}",
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }
        
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        analysis_text = response_body['content'][0]['text']
        
        logger.info(f"✅ Analyse terminée: {len(analysis_text)} caractères")
        
        # Generate PDF in memory
        logger.info("📄 Génération du PDF...")
        pdf_buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#dc3545'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#6c757d'),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        # Title
        story.append(Paragraph("🔍 ANALYSE DE RISQUES DE SÉCURITÉ", title_style))
        current_time = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
        story.append(Paragraph(f"Généré le {current_time}", subtitle_style))
        story.append(Spacer(1, 0.5*cm))
        
        # Add image to PDF
        try:
            img = Image.open(BytesIO(image_bytes))
            img_width, img_height = img.size
            aspect = img_height / float(img_width)
            
            # Resize image to fit in PDF (max 12cm width)
            display_width = 12*cm
            display_height = display_width * aspect
            
            # Save image to temporary buffer
            img_buffer = BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            rl_image = RLImage(img_buffer, width=display_width, height=display_height)
            story.append(rl_image)
            story.append(Spacer(1, 1*cm))
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de l'ajout de l'image au PDF: {e}")
        
        # Page break
        story.append(PageBreak())
        
        # Analysis content
        story.append(Paragraph("📋 ANALYSE DÉTAILLÉE", title_style))
        story.append(Spacer(1, 0.5*cm))
        
        # Parse and format analysis text
        lines = analysis_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.3*cm))
                continue
            
            # Escape XML special characters
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Detect headings
            if line.startswith('#') or line.startswith('**'):
                line = line.replace('#', '').replace('**', '').strip()
                heading_style = ParagraphStyle(
                    'Heading',
                    parent=styles['Heading2'],
                    fontSize=14,
                    textColor=colors.HexColor('#2563eb'),
                    spaceAfter=10,
                    spaceBefore=15
                )
                story.append(Paragraph(line, heading_style))
            # Detect bullet points
            elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
                line = '• ' + line[1:].strip()
                story.append(Paragraph(line, styles['Normal']))
            # Detect numbered lists
            elif len(line) > 2 and line[0].isdigit() and line[1] in '.):':
                story.append(Paragraph(line, styles['Normal']))
            else:
                story.append(Paragraph(line, styles['Normal']))
        
        # Footer
        story.append(Spacer(1, 1*cm))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#6c757d'),
            alignment=TA_CENTER
        )
        story.append(Paragraph("Rapport généré automatiquement par l'IA - TechnoPlast Safety Dashboard", footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF bytes
        pdf_buffer.seek(0)
        pdf_bytes = pdf_buffer.read()
        
        logger.info(f"✅ PDF généré: {len(pdf_bytes)} octets")
        
        # Return PDF as download
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=analyse_risques_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'analyse d'image: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}")

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

@app.post("/api/create-event-audio")
async def create_event_audio(request: dict):
    """Create event from audio transcription."""
    try:
        from event_creator import create_event
        from datetime import datetime
        
        description = request.get('description', '').strip()
        
        # Validation de la description
        if not description or len(description) < 10:
            raise HTTPException(
                status_code=400, 
                detail="La description doit contenir au moins 10 caractères"
            )
        
        logger.info(f"📝 Création d'événement avec description: {description[:100]}...")
        logger.info(f"   Type: {request.get('event_type', 'EHS')}")
        logger.info(f"   Classification: {request.get('classification', 'PREVENTIVE_DECLARATION')}")
        
        # Valeurs par défaut pour les événements créés par transcription audio
        DEFAULT_EMPLOYEE_ID = 1001  # Numéro d'employé par défaut
        DEFAULT_ORG_UNIT_ID = 126    # Unité organisationnelle par défaut
        
        event = create_event(
            declared_by_id=request.get('declared_by_id', DEFAULT_EMPLOYEE_ID),
            description=description,
            start_datetime=datetime.now(),
            organizational_unit_id=request.get('organizational_unit_id', DEFAULT_ORG_UNIT_ID),
            event_type=request.get('event_type', 'EHS'),
            classification=request.get('classification', 'PREVENTIVE_DECLARATION')
        )
        
        if event:
            logger.info(f"✅ Événement créé - ID: {event['event_id']}")
            return {
                "success": True,
                "event": dict(event),
                "message": "Événement créé avec succès"
            }
        else:
            raise HTTPException(status_code=500, detail="Échec de la création")
            
    except psycopg2_errors.ForeignKeyViolation as e:
        logger.error(f"❌ Erreur de clé étrangère: {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Erreur d'intégrité de la base de données: {str(e)}"
        )
    except ValueError as e:
        logger.error(f"❌ Erreur de validation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error creating event from audio: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcribe-audio")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """Transcribe audio file using AWS Transcribe."""
    try:
        S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "bucket-translator")
        REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        logger.info(f"🎤 Début de la transcription - Bucket: {S3_BUCKET_NAME}, Région: {REGION}")
        
        # Sauvegarder temporairement le fichier en respectant son type
        content = await audio_file.read()
        content_type = (audio_file.content_type or '').split(';')[0]
        ext = 'wav'
        if '/' in content_type:
            ext = content_type.split('/')[-1]
        # Normalisation simple
        if ext in ['x-wav', 'x-wav;codec=1']:
            ext = 'wav'
        if ext == 'mpeg':
            ext = 'mp3'
        allowed_exts = ['wav', 'mp3', 'webm', 'ogg', 'flac', 'mp4']
        if ext not in allowed_exts:
            ext = 'wav'

        temp_file = f"/tmp/audio_{uuid.uuid4()}.{ext}"
        with open(temp_file, "wb") as f:
            f.write(content)

        logger.info(f"📁 Fichier audio sauvegardé: {temp_file} ({len(content)} bytes), detected ext={ext}")

        # Upload vers S3
        s3_client = boto3.client('s3', region_name=REGION)
        transcribe_client = boto3.client('transcribe', region_name=REGION)

        job_name = f"event-transcription-{uuid.uuid4()}"
        file_key = f"event-audio/{job_name}.{ext}"

        logger.info(f"☁️ Upload vers S3: s3://{S3_BUCKET_NAME}/{file_key}")
        s3_client.upload_file(temp_file, S3_BUCKET_NAME, file_key)
        os.remove(temp_file)

        # Démarrer la transcription
        file_uri = f"s3://{S3_BUCKET_NAME}/{file_key}"
        logger.info(f"🚀 Démarrage du job Transcribe: {job_name} (format={ext})")

        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': file_uri},
            MediaFormat=ext,
            LanguageCode='fr-FR'
        )
        
        # Attendre le résultat
        max_wait = 60  # 60 secondes max
        waited = 0
        while waited < max_wait:
            status = transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            
            logger.info(f"⏳ Statut du job {job_name}: {job_status} (attendu: {waited}s)")
            
            if job_status == 'COMPLETED':
                transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                logger.info(f"📥 Récupération du résultat depuis: {transcript_uri}")
                
                result_response = requests.get(transcript_uri)
                result_data = result_response.json()
                
                # Debug: afficher la structure complète
                logger.info(f"🔍 DEBUG - Résultat complet: {json.dumps(result_data, indent=2)}")
                
                transcript_text = result_data['results']['transcripts'][0]['transcript']
                
                logger.info(f"🔍 DEBUG - Longueur transcription: {len(transcript_text)} caractères")
                logger.info(f"🔍 DEBUG - Transcription brute: '{transcript_text}'")
                logger.info(f"✅ Transcription réussie: {transcript_text[:100] if transcript_text else '(vide)'}...")
                
                # Nettoyage
                s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=file_key)
                
                # Si la transcription est vide, retourner une erreur
                if not transcript_text or len(transcript_text.strip()) == 0:
                    logger.warning("⚠️ La transcription est vide - l'audio ne contient probablement que du silence")
                    return {
                        "success": False,
                        "error": "La transcription est vide. Veuillez parler plus fort ou vérifier votre microphone."
                    }
                
                return {
                    "success": True,
                    "transcription": transcript_text,
                    "simulated": False
                }
            elif job_status == 'FAILED':
                failure_reason = status['TranscriptionJob'].get('FailureReason', 'Transcription failed')
                logger.error(f"❌ Transcription échouée: {failure_reason}")
                return {
                    "success": False,
                    "error": failure_reason
                }
            
            time.sleep(2)
            waited += 2
        
        logger.warning(f"⏰ Timeout après {max_wait}s")
        return {"success": False, "error": "Timeout - transcription trop longue"}
        
    except Exception as e:
        logger.error(f"❌ Error transcribing audio: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    print("🚀 Démarrage du serveur web sur http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

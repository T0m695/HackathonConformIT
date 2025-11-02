import os
import boto3
import base64
import json
import io
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.colors import HexColor

# --- CONFIGURATION ---

# Charger les variables du fichier .env
load_dotenv()

# Récupérer la région depuis .env, avec une valeur par défaut
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Modèle multimodal à utiliser (Claude 3 Sonnet est un bon équilibre)
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

# Le chemin vers l'image que vous voulez analyser
IMAGE_PATH = "image.jpg"

# Le nom du fichier PDF de sortie
OUTPUT_PDF = "analyse_risques.pdf"

# Le prompt : C'est ici que vous donnez vos instructions
PROMPT = """
Tu es un expert en sécurité industrielle et un analyste de risques. 
Regarde l'image fournie et effectue les tâches suivantes :

1.  **Description de la scène** : Décris brièvement ce qui se passe.
2.  **Identification des risques** : Liste tous les dangers ou risques potentiels visibles.
3.  **Analyse et Gravité** : Pour chaque risque, explique pourquoi c'est un problème et attribue un niveau de gravité (Élevé, Moyen, Faible).
4.  **Actions recommandées** : Suggère des mesures correctives immédiates.

Fournis la réponse dans un format clair et structuré.
"""


def generate_pdf_report(image_path, analysis_text, output_path):
    """Génère un rapport PDF avec l'image et l'analyse."""
    
    # Créer le document PDF
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Container pour les éléments du PDF
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Style pour le titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=HexColor('#dc3545'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Style pour le sous-titre
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#6c757d'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    # Style pour le contenu
    content_style = ParagraphStyle(
        'CustomContent',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        spaceAfter=12
    )
    
    # En-tête du document
    elements.append(Paragraph("🔍 RAPPORT D'ANALYSE DE RISQUES", title_style))
    elements.append(Paragraph(
        f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}",
        subtitle_style
    ))
    elements.append(Spacer(1, 1*cm))
    
    # Ajouter l'image analysée
    try:
        img = RLImage(image_path, width=12*cm, height=12*cm, kind='proportional')
        elements.append(img)
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(
            f"<i>Image source : {os.path.basename(image_path)}</i>",
            subtitle_style
        ))
    except Exception as e:
        print(f"⚠️ Impossible d'ajouter l'image au PDF : {e}")
    
    elements.append(Spacer(1, 1*cm))
    elements.append(PageBreak())
    
    # Titre de l'analyse
    elements.append(Paragraph("📋 ANALYSE DÉTAILLÉE", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Convertir le texte d'analyse en paragraphes
    # Nettoyer et formatter le texte pour ReportLab
    analysis_lines = analysis_text.split('\n')
    
    for line in analysis_lines:
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 0.3*cm))
            continue
        
        # Détection des titres (lignes qui commencent par des numéros ou **titre**)
        if line.startswith('#') or line.startswith('**'):
            # Titre de section
            line = line.replace('#', '').replace('**', '').strip()
            heading_style = ParagraphStyle(
                'Heading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=HexColor('#2563eb'),
                spaceAfter=10,
                spaceBefore=15,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph(line, heading_style))
        elif line.startswith(('1.', '2.', '3.', '4.', '•', '-', '*')):
            # Liste à puces ou numérotée
            elements.append(Paragraph(f"• {line[2:].strip()}", content_style))
        else:
            # Texte normal
            # Échapper les caractères spéciaux XML
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            elements.append(Paragraph(line, content_style))
    
    # Footer
    elements.append(Spacer(1, 2*cm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#6c757d'),
        alignment=TA_CENTER
    )
    elements.append(Paragraph(
        "Rapport généré automatiquement par l'IA - TechnoPlast Safety Dashboard",
        footer_style
    ))
    
    # Construire le PDF
    doc.build(elements)


# --- 1. INITIALISATION DU CLIENT ---
print(f"Connexion à Bedrock dans la région {AWS_REGION}...")
try:
    # Boto3 utilise automatiquement les clés AWS du .env
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=AWS_REGION
    )
except Exception as e:
    print(f"ERREUR : Impossible de créer le client Boto3. Vérifiez vos identifiants.")
    print(e)
    exit()

# --- 2. CHARGEMENT ET ENCODAGE DE L'IMAGE ---
print(f"Chargement de l'image : {IMAGE_PATH}...")
try:
    with Image.open(IMAGE_PATH) as image:
        # Déterminer le format (jpeg, png, etc.)
        image_format = image.format or "JPEG"
        media_type = f"image/{image_format.lower()}"

        # Convertir l'image en bytes
        with io.BytesIO() as buffer:
            image.save(buffer, format=image_format)
            image_bytes = buffer.getvalue()

        # Encoder l'image en Base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
except FileNotFoundError:
    print(f"ERREUR : Le fichier image '{IMAGE_PATH}' n'a pas été trouvé.")
    exit()
except Exception as e:
    print(f"ERREUR : Impossible de charger ou d'encoder l'image : {e}")
    exit()

# --- 3. PRÉPARATION DE LA REQUÊTE BEDROCK ---

# Structure du corps (body) pour Claude 3 Multimodal
body = json.dumps({
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 4096,  # Augmenter si vous attendez une analyse très détaillée
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64_image
                    }
                },
                {
                    "type": "text",
                    "text": PROMPT
                }
            ]
        }
    ]
})

# --- 4. APPEL À L'API BEDROCK ---
print(f"Envoi de la requête à {MODEL_ID}. L'analyse est en cours...")
try:
    # Invocation du modèle
    response = client.invoke_model(
        body=body,
        modelId=MODEL_ID,
        accept="application/json",
        contentType="application/json"
    )

    # --- 5. RÉCUPÉRATION ET AFFICHAGE DE LA RÉPONSE ---
    response_body = json.loads(response.get("body").read())
    
    # Extraire le texte de l'analyse
    analysis_text = response_body.get("content", [{}])[0].get("text", "")

    print("\n" + "="*50)
    print("🤖 ANALYSE DE RISQUES TERMINÉE 🤖")
    print("="*50 + "\n")
    print(analysis_text)
    
    # --- 6. GÉNÉRATION DU PDF ---
    print(f"\n📄 Génération du rapport PDF : {OUTPUT_PDF}...")
    generate_pdf_report(IMAGE_PATH, analysis_text, OUTPUT_PDF)
    print(f"✅ Rapport PDF généré avec succès : {OUTPUT_PDF}")

except Exception as e:
    print(f"\nERREUR lors de l'appel à Bedrock : {e}")
    print("Veuillez vérifier les points suivants :")
    print(f"1. Avez-vous activé l'accès au modèle '{MODEL_ID}' dans la console AWS Bedrock ?")
    print(f"2. Votre région '{AWS_REGION}' est-elle correcte ?")
    print("3. Vos clés AWS ont-elles les permissions 'bedrock:InvokeModel' ?")

"""
Générateur de rapport CNESST depuis une page web avec analyse LLM
"""
import os
import json
import boto3
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter

load_dotenv()


# Mapping complet des champs
CHAMP_MAPPING_PDF = {
    "date_enquete": "S00_Date1",
    "nom_enqueteur": "S01_Texte_Nom1",
    "fonction_enqueteur": "S01_Texte_Fonction1",
    "nom_enqueteur_2": "S01_Texte_Nom2",
    "fonction_enqueteur_2": "S01_Texte_Fonction2",
    "nom_enqueteur_3": "S01_Texte_Nom3",
    "fonction_enqueteur_3": "S01_Texte_Fonction3",
    "nom_employeur": "S02_Texte_Nom",
    "adresse_employeur": "S02_Texte_Adresse",
    "nom_etablissement": "S03_Texte_Nom",
    "nom_responsable_etablissement": "S03_Texte_Nom-fonction",
    "adresse_etablissement": "S03_Texte_coordonnees",
    "nom_travailleur": "S04_Texte_Nom",
    "adresse_travailleur": "S04_Texte_coordonnees",
    "metier_travailleur": "S04_Texte_metier",
    "employeur_travailleur": "S04_Texte_emp",
    "anciennete_travailleur": "S04_Texte_anc",
    "date_naissance_travailleur": "S04_Date1",
    "date_embauche_travailleur": "S04_Date2",
    "experience_travailleur": "S04_Texte_années",
    "date_accident": "S05_Date1",
    "heure_accident": "S05_Texte_heure",
    "description_blessure": "S05_Texte_bles",
    "precision_accident_1": "S05_Texte_prec1",
    "precision_accident_2": "S05_Texte_prec2",
    "precision_accident_3": "S05_Texte_prec3",
    "precision_accident_4": "S05_Texte_prec4",
    "precision_accident_5": "S05_Texte_prec5",
    "precision_accident_6": "S05_Texte_prec6",
    "precision_accident_7": "S05_Texte_prec7",
    "description_tache": "S05_Texte_desc",
    "endroit_secteur": "S06_Texte_desc1",
    "description_complete_accident": "S07_Texte_desc2",
    "fait_individu": "S07_Texte_desc3",
    "fait_tache": "S07_Texte_desc4",
    "fait_environnement": "S07_Texte_desc5",
    "fait_materiel": "S08_Texte_desc1",
    "cause_1": "S08_Texte_lien",
    "mesure_1": "S08_Texte_desc2",
    "responsable_1": "S08_Texte_resp",
    "echeance_1": "S08_Date",
    "echeance_texte_1": "S08_Texte_eche",
    "cause_2": "S09_Texte_desc1",
    "lien_cause_2": "S09_Texte_lien",
    "mesure_2": "S09_Texte_desc2",
    "responsable_2": "S09_Texte_resp",
    "echeance_2": "S09_Date",
    "echeance_texte_2": "S09_Texte_eche",
    "cause_3": "S10_Texte_desc1",
    "lien_cause_3": "S10_Texte_lien",
    "mesure_3": "S10_Texte_desc2",
    "responsable_3": "S10_Texte_resp",
    "echeance_3": "S10_Date",
    "echeance_texte_3": "S10_Texte_eche",
    "signature_enqueteur_nom": "S11_Texte_nom",
    "signature_enqueteur_fonction": "S11_Texte_fonc",
    "signature_enqueteur_adresse": "S11_Texte_add",
    "signature_enqueteur_telephone": "S11_Telephone",
    "signature_enqueteur_date": "S11_Date",
    "approbation_elements": "S12_Texte_elem",
    "approbation_date": "S12_Date",
    "signature_representant_nom": "S13_Texte_nom",
    "signature_representant_date": "S13_Date",
    "signature_employeur_nom": "S14_Texte_nom",
    "signature_employeur_date": "S14_Date",
}


def analyser_description_avec_llm(description_accident: str, donnees_contexte: dict):
    """
    Utilise AWS Bedrock pour analyser la description de l'accident
    et générer automatiquement l'analyse ITEM, les causes et les mesures correctives.
    """
    
    # Configuration AWS
    aws_config = {
        'region_name': os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY"),
    }
    
    if token := os.getenv("AWS_SESSION_TOKEN"):
        aws_config['aws_session_token'] = token
    
    bedrock = boto3.client('bedrock-runtime', **aws_config)
    
    # Contexte de l'incident
    contexte = f"""
Travailleur: {donnees_contexte.get('nom_travailleur', 'N/A')}
Métier: {donnees_contexte.get('metier_travailleur', 'N/A')}
Date accident: {donnees_contexte.get('date_accident', 'N/A')}
Heure: {donnees_contexte.get('heure_accident', 'N/A')}
Lieu: {donnees_contexte.get('endroit_secteur', 'N/A')}
"""
    
    system_prompt = """Tu es un expert en santé et sécurité au travail, spécialisé dans l'analyse d'accidents selon la méthode ITEM (Individu-Tâche-Environnement-Matériel) et l'identification de causes racines avec mesures correctives.

Ton rôle est d'analyser des descriptions d'accidents et de produire une analyse structurée pour un rapport CNESST.

Tu dois retourner UNIQUEMENT un objet JSON valide avec cette structure exacte (sans markdown, sans explication):
{
  "fait_individu": "Analyse des facteurs liés à la personne (formation, expérience, EPI, état physique/mental)",
  "fait_tache": "Analyse de la tâche effectuée (procédures, méthode de travail, risques connus)",
  "fait_environnement": "Analyse de l'environnement (éclairage, bruit, température, accès, encombrement)",
  "fait_materiel": "Analyse du matériel et équipements (état, conformité, entretien)",
  "precision_accident_1": "Première précision clé sur l'accident",
  "precision_accident_2": "Deuxième précision clé",
  "precision_accident_3": "Troisième précision clé",
  "cause_1": "Première cause identifiée",
  "mesure_1": "Mesure corrective pour la cause 1",
  "responsable_1": "Responsable de la mesure 1",
  "echeance_texte_1": "Échéance pour mesure 1",
  "cause_2": "Deuxième cause identifiée",
  "lien_cause_2": "Lien avec les autres causes",
  "mesure_2": "Mesure corrective pour la cause 2",
  "responsable_2": "Responsable de la mesure 2",
  "echeance_texte_2": "Échéance pour mesure 2",
  "cause_3": "Troisième cause (cause racine si possible)",
  "lien_cause_3": "Lien avec les autres causes",
  "mesure_3": "Mesure corrective pour la cause 3",
  "responsable_3": "Responsable de la mesure 3",
  "echeance_texte_3": "Échéance pour mesure 3"
}"""
    
    user_message = f"""Contexte de l'accident:
{contexte}

Description complète de l'accident:
{description_accident}

Analyse cet accident selon la méthode ITEM et identifie 3 causes avec leurs mesures correctives.
Retourne UNIQUEMENT le JSON, sans aucun texte avant ou après."""
    
    try:
        print("🤖 Appel à AWS Bedrock pour analyse LLM...")
        
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
                "temperature": 0.3
            })
        )
        
        response_body = json.loads(response['body'].read())
        ai_text = response_body['content'][0]['text']
        
        print("✅ Réponse LLM reçue")
        print(f"📝 Extrait: {ai_text[:200]}...")
        
        # Extraire le JSON de la réponse
        if '{' in ai_text and '}' in ai_text:
            json_start = ai_text.index('{')
            json_end = ai_text.rindex('}') + 1
            json_str = ai_text[json_start:json_end]
            analyse = json.loads(json_str)
            
            print(f"✅ Analyse extraite: {len(analyse)} champs générés par le LLM")
            return analyse
        else:
            print("⚠️ Pas de JSON trouvé dans la réponse")
            return {}
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse LLM: {e}")
        return {}


def recuperer_donnees_depuis_page(donnees_page: dict):
    """
    Récupère les données depuis une page web (dict passé en paramètre).
    
    Structure attendue:
    {
        "nom_travailleur": "Jean Dupont",
        "metier_travailleur": "Électricien",
        "date_accident": "2025-10-28",
        "heure_accident": "14:30",
        "endroit_secteur": "Local technique A",
        "description_complete_accident": "Description détaillée de ce qui s'est passé...",
        "description_blessure": "Brûlures main droite",
        ... autres champs disponibles sur la page
    }
    """
    
    print(f"📄 Récupération des données depuis la page...")
    print(f"📊 {len(donnees_page)} champs reçus")
    
    # Extraire la description pour l'analyse LLM
    description_accident = donnees_page.get('description_complete_accident', '')
    
    if not description_accident:
        print("⚠️ Aucune description d'accident trouvée")
        return donnees_page
    
    print(f"📝 Description de l'accident: {len(description_accident)} caractères")
    
    # Appeler le LLM pour analyser la description
    analyse_llm = analyser_description_avec_llm(description_accident, donnees_page)
    
    # Fusionner les données de la page avec l'analyse LLM
    donnees_completes = {**donnees_page, **analyse_llm}
    
    print(f"✅ Données complètes: {len(donnees_completes)} champs")
    
    return donnees_completes


def generer_rapport_pdf(donnees: dict, output_filename: str = "Rapport_CNESST.pdf"):
    """
    Génère le PDF CNESST avec les données fournies.
    """
    template_pdf_path = "formulaire.pdf"
    
    # Mapper les données vers les champs du PDF
    data_for_pdf = {}
    for data_key, pdf_field in CHAMP_MAPPING_PDF.items():
        if data_key in donnees and donnees[data_key] is not None:
            data_for_pdf[pdf_field] = str(donnees[data_key])
    
    print(f"📄 Champs mappés pour PDF: {len(data_for_pdf)} champs")
    
    # Lire le PDF template
    reader = PdfReader(template_pdf_path)
    writer = PdfWriter()
    
    # Copier toutes les pages
    for page in reader.pages:
        writer.add_page(page)
    
    # Remplir les champs du formulaire
    try:
        writer.update_page_form_field_values(writer.pages[0], data_for_pdf)
        print("✅ Champs du formulaire remplis")
    except Exception as e:
        print(f"⚠️ Erreur lors du remplissage: {e}")
    
    # Écrire le PDF de sortie
    with open(output_filename, 'wb') as output_file:
        writer.write(output_file)
    
    print(f"✅ PDF généré: {output_filename}")
    
    return output_filename


def generer_rapport_depuis_page(donnees_page: dict, output_filename: str = None):
    """
    Point d'entrée principal:
    1. Récupère les données de la page
    2. Analyse la description avec le LLM
    3. Génère le PDF complet
    """
    
    print("="*60)
    print("🚀 GÉNÉRATION DE RAPPORT CNESST DEPUIS PAGE WEB")
    print("="*60)
    
    # Étape 1: Récupérer et enrichir les données
    donnees_completes = recuperer_donnees_depuis_page(donnees_page)
    
    # Étape 2: Générer le PDF
    if output_filename is None:
        incident_id = donnees_page.get('incident_id', 'unknown')
        output_filename = f"Rapport_CNESST_{incident_id}.pdf"
    
    pdf_path = generer_rapport_pdf(donnees_completes, output_filename)
    
    print("="*60)
    print(f"🎉 RAPPORT GÉNÉRÉ AVEC SUCCÈS: {pdf_path}")
    print("="*60)
    
    return pdf_path


# Exemple d'utilisation
if __name__ == "__main__":
    # Simulation de données récupérées depuis une page web
    donnees_page_web = {
        # Données de base récupérées depuis la page
        "incident_id": "123",
        "date_enquete": "2025-11-01",
        "nom_enqueteur": "Michel Tremblay",
        "fonction_enqueteur": "Représentant SST",
        "nom_enqueteur_2": "Caroline Gagnon",
        "fonction_enqueteur_2": "Représentante employeur",
        
        "nom_employeur": "Construction ABC Inc.",
        "adresse_employeur": "123 rue Principale, Saguenay, G7H 2B4",
        
        "nom_etablissement": "Chantier XYZ",
        "adresse_etablissement": "456 boul. Talbot, Saguenay, G7H 4K9",
        "nom_responsable_etablissement": "Sophie Martin, Contremaître",
        
        "nom_travailleur": "Jean Dupont",
        "adresse_travailleur": "789 rue des Érables, Chicoutimi, G7G 1A1",
        "metier_travailleur": "Électricien",
        "employeur_travailleur": "Construction ABC Inc.",
        "anciennete_travailleur": "2 ans",
        "date_naissance_travailleur": "1990-05-15",
        "date_embauche_travailleur": "2023-10-01",
        "experience_travailleur": "5 ans",
        
        "date_accident": "2025-10-28",
        "heure_accident": "14:30",
        "description_blessure": "Brûlures mineures main droite",
        
        "endroit_secteur": "Local technique A, panneau électrique P-101",
        "description_tache": "Remplacement d'un disjoncteur sur le panneau P-101",
        
        # DESCRIPTION COMPLÈTE - Le LLM va analyser cette partie
        "description_complete_accident": """
En retirant l'ancien disjoncteur du panneau électrique P-101, un arc électrique s'est produit 
causant des brûlures mineures à la main droite du travailleur Jean Dupont.

Le travailleur effectuait le remplacement d'un disjoncteur défectueux dans le local technique A.
Il portait des gants de travail standards mais n'avait pas utilisé la procédure de cadenassage 
LOTO (Lock Out Tag Out) car il considérait la tâche comme rapide.

Le disjoncteur était ancien (modèle de 1998) et les outils utilisés n'étaient pas isolés pour 
le voltage requis (600V). Le panneau était sous tension lors de l'intervention.

Le travailleur a une formation en cadenassage datant de mars 2024, mais par habitude et pression 
du temps, il a choisi de ne pas l'appliquer pour cette intervention "simple".

L'environnement de travail était bien éclairé (500 lux) et la température ambiante était normale (22°C).
Il n'y avait pas d'équipement de cadenassage facilement accessible près du panneau électrique.
""",
        
        # Signatures (déjà disponibles)
        "signature_enqueteur_nom": "Michel Tremblay",
        "signature_enqueteur_fonction": "Représentant SST",
        "signature_enqueteur_adresse": "123 rue Principale, Saguenay",
        "signature_enqueteur_telephone": "418-555-1234",
        "signature_enqueteur_date": "2025-11-01",
        
        "approbation_elements": "Enquête complète et mesures correctives approuvées",
        "approbation_date": "2025-11-01",
        
        "signature_representant_nom": "Caroline Gagnon",
        "signature_representant_date": "2025-11-01",
        
        "signature_employeur_nom": "Robert Lavoie, Directeur",
        "signature_employeur_date": "2025-11-01"
    }
    
    # Générer le rapport
    resultat = generer_rapport_depuis_page(donnees_page_web)
    print(f"\n✅ Fichier généré: {resultat}")

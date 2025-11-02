import boto3
import time
import uuid
import os
import requests
import json
from dotenv import load_dotenv

# --- Modules pour l'enregistrement audio ---
import sounddevice as sd
import soundfile as sf

# === Configuration ===
# ▼▼▼ MODIFIEZ CECI avec le nom de votre bucket S3 ▼▼▼
S3_BUCKET_NAME = "bucket-translator"
# ▲▲▲ MODIFIEZ CECI ▲▲▲

REGION = "us-east-1"      # La région de votre test précédent
RECORD_DURATION = 5       # Durée de l'enregistrement en secondes
LOCAL_FILE_NAME = "recording.wav"
SAMPLE_RATE = 44100       # Qualité CD
# ======================


def record_audio():
    """Enregistre l'audio du micro et le sauvegarde localement."""
    print(f"Début de l'enregistrement de {RECORD_DURATION} secondes...")
    print("PARLEZ MAINTENANT !")
    
    # Enregistrement
    recording = sd.rec(int(RECORD_DURATION * SAMPLE_RATE), 
                       samplerate=SAMPLE_RATE, 
                       channels=1,  # Mono
                       dtype='float32')
    
    sd.wait()  # Attend la fin de l'enregistrement

    # Sauvegarde du fichier
    sf.write(LOCAL_FILE_NAME, recording, SAMPLE_RATE)
    print(f"Audio sauvegardé sous : {LOCAL_FILE_NAME}")


def transcribe_and_get_output():
    """Envoie l'audio à Transcribe, attend, et affiche le résultat."""
    # 1. Initialiser les clients AWS
    s3_client = boto3.client('s3', region_name=REGION)
    transcribe_client = boto3.client('transcribe', region_name=REGION)

    # 2. Uploader le fichier sur S3
    job_name = f"test-job-{uuid.uuid4()}"
    file_key = f"audio-tests/{job_name}.wav"
    
    print(f"Upload du fichier vers S3 (s3://{S3_BUCKET_NAME}/{file_key})...")
    try:
        s3_client.upload_file(LOCAL_FILE_NAME, S3_BUCKET_NAME, file_key)
    except Exception as e:
        print(f"Erreur d'upload S3 : {e}")
        return

    # 3. Démarrer le job Transcribe
    file_uri = f"s3://{S3_BUCKET_NAME}/{file_key}"
    print("Démarrage du job Amazon Transcribe...")
    
    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': file_uri},
        MediaFormat='wav',
        LanguageCode='fr-FR'  # Changez si vous parlez une autre langue
    )

    # 4. Attendre (poller) la fin du job
    print("Traitement en cours... (cela peut prendre un moment)")
    while True:
        try:
            status = transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            
            if job_status in ['COMPLETED', 'FAILED']:
                print(f"Job terminé avec le statut : {job_status}")
                break
                
            print("Statut actuel : IN_PROGRESS... Attente de 5s.")
            time.sleep(5)
            
        except Exception as e:
            print(f"Erreur lors de la vérification du statut : {e}")
            break

    # 5. Récupérer et afficher le résultat
    if job_status == 'COMPLETED':
        transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
        
        # Télécharger le fichier JSON de résultats
        result_response = requests.get(transcript_uri)
        result_data = result_response.json()
        
        # Extraire le texte
        transcript_text = result_data['results']['transcripts'][0]['transcript']
        
        print("\n--- OUTPUT TRANSCRIPTION ---")
        print(transcript_text)
        print("----------------------------\n")
        
    elif job_status == 'FAILED':
        print(f"Le job a échoué : {status['TranscriptionJob']['FailureReason']}")
        
    # Nettoyage (optionnel)
    print("Nettoyage des fichiers...")
    os.remove(LOCAL_FILE_NAME)
    s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=file_key)
    print("Terminé.")


# --- Exécution principale ---
if __name__ == "__main__":
    # Charger les variables d'environnement (AWS_ACCESS_KEY_ID, etc.)
    load_dotenv()
    
    record_audio()
    transcribe_and_get_output()
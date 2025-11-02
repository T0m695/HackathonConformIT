"""
Script pour uploader les fichiers CSV vers S3 pour AWS Bedrock Knowledge Base
"""
import boto3
import os
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

def upload_csv_to_s3():
    """Upload tous les fichiers CSV vers S3."""
    
    # Configuration
    bucket_name = input("Nom du bucket S3: ").strip()
    prefix = input("Préfixe/dossier dans S3 (ex: rag-data): ").strip() or "rag-data"
    csv_dir = "csv_exports"
    
    if not bucket_name:
        print("❌ Nom du bucket requis!")
        return
    
    # Initialiser le client S3
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
            region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        # Vérifier que le bucket existe
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Bucket '{bucket_name}' trouvé\n")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"❌ Bucket '{bucket_name}' n'existe pas!")
        elif error_code == '403':
            print(f"❌ Accès refusé au bucket '{bucket_name}'")
        else:
            print(f"❌ Erreur: {e}")
        return
    
    # Lister les fichiers CSV
    if not os.path.exists(csv_dir):
        print(f"❌ Dossier '{csv_dir}' non trouvé!")
        print("Exécutez d'abord: python export_to_csv.py")
        return
    
    csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"❌ Aucun fichier CSV trouvé dans '{csv_dir}'")
        return
    
    print(f"📂 {len(csv_files)} fichiers CSV trouvés\n")
    
    # Demander confirmation
    print("Fichiers à uploader:")
    for f in csv_files:
        file_path = os.path.join(csv_dir, f)
        size_kb = os.path.getsize(file_path) / 1024
        print(f"  - {f} ({size_kb:.1f} KB)")
    
    print(f"\nDestination: s3://{bucket_name}/{prefix}/\n")
    
    confirm = input("Continuer? (o/n): ").strip().lower()
    if confirm not in ['o', 'oui', 'y', 'yes']:
        print("❌ Annulé")
        return
    
    # Upload des fichiers
    uploaded = 0
    failed = 0
    
    print("\n🚀 Début de l'upload...\n")
    
    for filename in csv_files:
        local_path = os.path.join(csv_dir, filename)
        s3_key = f"{prefix}/{filename}" if prefix else filename
        
        try:
            # Upload avec metadata
            s3_client.upload_file(
                local_path,
                bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'text/csv',
                    'Metadata': {
                        'source': 'export_to_csv.py',
                        'project': 'ConformIT'
                    }
                }
            )
            
            print(f"✅ {filename} → s3://{bucket_name}/{s3_key}")
            uploaded += 1
            
        except ClientError as e:
            print(f"❌ Échec pour {filename}: {e}")
            failed += 1
    
    # Résumé
    print(f"\n{'='*60}")
    print("UPLOAD TERMINÉ")
    print("="*60)
    print(f"✅ Réussis: {uploaded}/{len(csv_files)}")
    if failed > 0:
        print(f"❌ Échecs: {failed}/{len(csv_files)}")
    
    print(f"\n📍 URL S3: s3://{bucket_name}/{prefix}/")
    
    print("\n🎯 Prochaines étapes:")
    print("1. Créez une Knowledge Base dans AWS Bedrock Console")
    print(f"2. Configurez la source S3: s3://{bucket_name}/{prefix}/")
    print("3. Notez le Knowledge Base ID")
    print("4. Ajoutez KNOWLEDGE_BASE_ID dans votre fichier .env")
    print("5. Testez avec: python main.py")

if __name__ == "__main__":
    print("="*60)
    print("UPLOAD CSV VERS S3 POUR BEDROCK KNOWLEDGE BASE")
    print("="*60 + "\n")
    
    upload_csv_to_s3()

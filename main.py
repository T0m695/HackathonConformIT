import os
from dotenv import load_dotenv
from agent import EventAgent
from database import init_database

def main():
    """Point d'entrée principal de l'application."""
    # Charge les variables d'environnement
    load_dotenv()
    
    # Initialise la base de données depuis data/events.sql
    print("Initialisation de la base de données...")
    init_database()
    
    # Vérifie les credentials AWS
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    if not aws_access_key or not aws_secret_key:
        print("❌ ERREUR: AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY doivent être définis dans .env")
        print("\nPour corriger cela :")
        print("1. Ouvrez votre terminal AWS CLI ou console AWS")
        print("2. Exécutez: aws sts get-session-token")
        print("3. Copiez les credentials dans votre fichier .env")
        return
    
    if not aws_session_token:
        print("⚠️  ATTENTION: AWS_SESSION_TOKEN non défini. Cela peut causer des erreurs d'authentification.")
        print("Pour obtenir de nouveaux credentials temporaires :")
        print("1. aws sts get-session-token")
        print("2. Mettez à jour votre .env avec les nouveaux credentials")
    
    # Initialise l'agent
    print("\n🚀 Initialisation de l'agent IA avec AWS Bedrock...")
    try:
        agent = EventAgent()
        
        # Test rapide de connexion
        print("🔍 Test de la connexion AWS...")
        test_response = agent.test_bedrock_connection()
        if not test_response:
            print("❌ Échec du test de connexion AWS Bedrock")
            print("💡 Solutions possibles :")
            print("   - Renouvelez vos credentials AWS")
            print("   - Vérifiez que vous avez accès à Bedrock")
            print("   - Assurez-vous que la région est correcte")
            return
            
        print(f"\n✅ Agent initialisé avec {len(agent.events)} événements")
        print(f"✅ Connexion AWS Bedrock validée")
        print(f"✅ Modèle: Claude 3 Haiku")
        print(f"✅ Région: {aws_region}")
        
        # Affiche les catégories disponibles
        categories = agent.get_all_categories()
        if categories:
            print(f"✅ Catégories disponibles: {', '.join(categories)}")
        
        print("\n" + "="*50)
        print("🤖 Agent IA de Recommandation d'Événements")
        print("="*50)
        print("\nTapez 'quit' pour quitter")
        print("Tapez 'test' pour tester la connexion")
        print()
        
        # Boucle interactive
        while True:
            user_input = input("Vous: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Au revoir!")
                break
                
            if user_input.lower() == 'test':
                print("🔍 Test de connexion...")
                if agent.test_bedrock_connection():
                    print("✅ Connexion OK")
                else:
                    print("❌ Connexion échouée")
                continue
            
            if not user_input:
                continue
            
            print("\n🤖 Agent: ", end="")
            response = agent.search_events(user_input)
            print(response)
            print()
            
    except Exception as e:
        print(f"\n❌ Erreur lors de l'initialisation: {str(e)}")
        print("\n🔧 Guide de dépannage :")
        print("1. Credentials expirés : Exécutez 'aws sts get-session-token'")
        print("2. Accès Bedrock : Vérifiez dans la console AWS > Bedrock")
        print("3. Région incorrecte : Changez AWS_DEFAULT_REGION dans .env")
        print("4. Permissions IAM : Vérifiez vos permissions Bedrock")

if __name__ == "__main__":
    main()

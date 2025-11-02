-- Vérifier l'encodage actuel de la base
SELECT 
    datname, 
    pg_encoding_to_char(encoding) as encoding,
    datcollate,
    datctype
FROM pg_database 
WHERE datname = 'hackathon';

-- Vérifier l'encodage du serveur
SHOW server_encoding;
SHOW client_encoding;

-- Si nécessaire, recréer la base avec le bon encodage
-- ATTENTION: Ceci supprime toutes les données!
-- DROP DATABASE hackathon;
-- CREATE DATABASE hackathon 
--     WITH ENCODING 'UTF8' 
--     LC_COLLATE='fr_FR.UTF-8' 
--     LC_CTYPE='fr_FR.UTF-8' 
--     TEMPLATE=template0;

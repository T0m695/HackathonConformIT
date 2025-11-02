#!/bin/bash
set -e

# Attendre que PostgreSQL soit prêt
until PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  echo "🔄 PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "✅ PostgreSQL is up - importing database"

# Supprimer la ligne transaction_timeout et importer le SQL
sed '/transaction_timeout/d' /docker-entrypoint-initdb.d/events.sql | PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "✅ Database import completed"
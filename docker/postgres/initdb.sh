#!/bin/bash
set -e

echo "🔁 initdb script starting..."

BACKUP_PATH="/docker-entrypoint-initdb.d/events.backup"

if [ -f "$BACKUP_PATH" ]; then
  echo "🔁 events.backup detected"
  echo "📄 File size: $(ls -lh "$BACKUP_PATH" | awk '{print $5}')"
  
  # Vérifier si c'est un dump PostgreSQL custom format (commence par "PGDMP")
  if head -c 5 "$BACKUP_PATH" | grep -q "PGDMP"; then
    echo "🗜️ Detected PostgreSQL custom format dump"
    echo "📦 Restoring with pg_restore..."
    pg_restore --verbose --no-acl --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$BACKUP_PATH"
    echo "✅ Restore completed successfully"
  else
    echo "📝 Not a custom format, trying as plain SQL..."
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$BACKUP_PATH"
    echo "✅ SQL file executed successfully"
  fi
  
  # Vérifier que les tables ont été créées
  echo "🔍 Verifying restore..."
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt" || echo "⚠️ No tables found"
  
else
  echo "⚠️ No events.backup found at $BACKUP_PATH, skipping restore."
fi

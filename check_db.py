import sqlite3

conn = sqlite3.connect('events.db')
cursor = conn.cursor()

# Vérifier les tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', [t[0] for t in tables])

# Vérifier le contenu de events
cursor.execute('SELECT COUNT(*) FROM events')
print('Lignes dans events:', cursor.fetchone()[0])

conn.close()

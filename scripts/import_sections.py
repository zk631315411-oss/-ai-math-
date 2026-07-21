import sqlite3, gzip, base64

dst = '/opt/ai-math/data/learning.db'
b64_path = '/opt/ai-math/data/sections_dump.b64'

with open(b64_path, 'r') as f:
    data = f.read()

sql = gzip.decompress(base64.b64decode(data)).decode('utf-8')

conn = sqlite3.connect(dst)
conn.executescript(sql)
conn.commit()
conn.close()

c = sqlite3.connect(dst).execute("SELECT COUNT(*) FROM textbook_sections").fetchone()[0]
print(f'Imported {c} rows into textbook_sections')

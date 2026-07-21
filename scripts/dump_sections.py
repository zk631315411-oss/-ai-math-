import sqlite3, gzip, base64

src = 'd:/ai-math/data/learning.db'
conn = sqlite3.connect(src)
rows = list(conn.execute('SELECT * FROM textbook_sections'))
conn.close()

lines = []
for r in rows:
    vals = []
    for v in r:
        if v is None:
            vals.append('NULL')
        elif isinstance(v, (int, float)):
            vals.append(str(v))
        else:
            escaped = str(v).replace("'", "''")
            vals.append(f"'{escaped}'")
    lines.append(f'INSERT OR REPLACE INTO textbook_sections VALUES ({",".join(vals)});')

sql = '\n'.join(lines)
data = base64.b64encode(gzip.compress(sql.encode('utf-8'))).decode('ascii')

with open('d:/ai-math/data/sections_dump.b64', 'w') as f:
    f.write(data)

print(f'{len(lines)} rows, {len(sql):,} bytes SQL -> {len(data):,} bytes b64')

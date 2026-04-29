import sqlite3

conn = sqlite3.connect('visitors.db')
c = conn.cursor()

cols_to_add = [
    'ALTER TABLE visitors ADD COLUMN status TEXT NOT NULL DEFAULT "completed"',
    'ALTER TABLE visitors ADD COLUMN peak_count INTEGER NOT NULL DEFAULT 1',
    'ALTER TABLE visitors ADD COLUMN start_time TEXT',
    'ALTER TABLE visitors ADD COLUMN end_time TEXT',
    'ALTER TABLE visitors ADD COLUMN duration_seconds INTEGER',
    'ALTER TABLE visitors ADD COLUMN starred INTEGER NOT NULL DEFAULT 0',
]

for sql in cols_to_add:
    try:
        c.execute(sql)
        print('Added:', sql[27:50])
    except Exception as e:
        print('Skipped (already exists):', e)

conn.commit()
conn.close()
print('Done! Database is ready.')
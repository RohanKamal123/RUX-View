import asyncio, asyncpg, ssl

async def t():
    conn = await asyncpg.connect(
        'postgresql://neondb_owner:npg_zvfiB9HruGl7@ep-blue-cake-aqmd63jn.c-8.us-east-1.aws.neon.tech/neondb?ssl=require',
        ssl=ssl.create_default_context(),
    )
    print('CONNECT OK', await conn.fetchval('SELECT 1'))
    rows = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    print('TABLES:', [r['table_name'] for r in rows])
    await conn.close()

asyncio.run(t())
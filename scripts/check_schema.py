#!/usr/bin/env python3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DATABASE_HOST', 'localhost'),
    port=int(os.getenv('DATABASE_PORT', 5432)),
    database=os.getenv('DATABASE_NAME', 'kolmo_db'),
    user=os.getenv('DATABASE_USER', 'postgres'),
    password=os.getenv('DATABASE_PASSWORD', 'postgres')
)

cursor = conn.cursor()
cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='mcol1_external_data' ORDER BY ordinal_position")
columns = cursor.fetchall()
print('Columns in mcol1_external_data:')
for col in columns:
    print(f'  - {col[0]}')
cursor.close()
conn.close()

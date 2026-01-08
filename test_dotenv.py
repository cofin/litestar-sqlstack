import os
from dotenv import load_dotenv
from pathlib import Path

env_content = """
POSTGRES_PORT=5432
DATABASE_PORT=${POSTGRES_PORT}
"""
with open("test.env", "w") as f:
    f.write(env_content)

load_dotenv("test.env", override=True)
print(f"POSTGRES_PORT: {os.getenv('POSTGRES_PORT')}")
print(f"DATABASE_PORT: {os.getenv('DATABASE_PORT')}")
os.remove("test.env")

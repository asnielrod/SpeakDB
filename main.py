import os
import psycopg2
import openai
from dotenv import load_dotenv
from fastapi import FastAPI
from openai import Completion
from typing import Optional, Dict

app = FastAPI()

load_dotenv()

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
openai_model = "text-davinci-002"

# Conexión a PostgreSQL
db_name = os.getenv("DB_NAME")  
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASSWORD")  
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

conn = psycopg2.connect(
    dbname=db_name, 
    user=db_user, 
    password=db_pass, 
    host=db_host, 
    port=db_port
)

# Información de la base de datos
db_info: Dict[str, Dict[str, Dict]] = {}


@app.on_event("startup")
async def startup_event():
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    table_names = [row[0] for row in cursor.fetchall()]
    
    db_info[db_name] = {}
    for table in table_names:
        cursor.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}';")
        db_info[db_name][table] = {row[0]: row[1] for row in cursor.fetchall()}


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/query/")
async def get_query(database: Optional[str] = None, natural_language_query: Optional[str] = None, page: int = 1, page_size: int = 50):
    if natural_language_query is None:
        return {"error": "No query provided"}

    if database is None or database not in db_info:
        return {"error": "Invalid or no database provided"}

    database_info = db_info[database]
    database_prompt = f"db name: '{database}', data structure: {database_info}"

    try:
        response = openai.Completion.create(
            engine=openai_model,
            prompt=f"Eres un asistente de inteligencia artificial diseñado para convertir consultas en lenguaje natural a consultas SQL para PostgreSQL. Aquí está tu tarea:\n{natural_language_query}\n{database_prompt}\nSQL:",
            temperature=0.1,  # reduce randomness
            max_tokens=200  # increase max tokens
        )
    except Exception as e:
        return {"error": f"Error during query generation: {e}"}

    sql_query = response.choices[0].text.strip()
    sql_query = f"{sql_query} OFFSET {page_size * (page - 1)} LIMIT {page_size}"  # add pagination

    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        if sql_query.lower().startswith("select"):
            rows = cursor.fetchall()
            return {"Query results": rows}
        conn.commit()
    except Exception as e:
        conn.rollback()
        return {"error": f"Error during database query: {e}"}

    return {"message": "Query executed successfully"}

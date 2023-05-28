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
openai_model = "text-davinci-002"  # El modelo de OpenAI que desea usar (esto puede variar)

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

# Almacenar la información de la base de datos y las tablas en una variable
db_info: Dict[str, Dict[str, Dict]] = {}


@app.on_event("startup")
async def startup_event():
    # Obtener la información de todas las tablas en la base de datos conectada
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
async def get_query(database: Optional[str] = None, natural_language_query: Optional[str] = None):
    if natural_language_query is None:
        return {"error": "No query provided"}

    # Asegurarse de que se proporciona una base de datos y de que está en la lista de bases de datos disponibles
    if database is None or database not in db_info:
        return {"error": "Invalid or no database provided"}

    # Añadir la información de la base de datos a la consulta
    database_info = db_info[database]
    database_prompt = f"db name: '{database}', data structure: {database_info}"

    # Convertir la consulta en lenguaje natural a SQL usando GPT-4
    try:
        response = openai.Completion.create(
            engine=openai_model,
            prompt=f"Eres un asistente de inteligencia artificial diseñado para convertir consultas en lenguaje natural a consultas SQL para PostgreSQL. Aquí está tu tarea:\n{natural_language_query}\n{database_prompt}\nSQL:",
            temperature=0.3,
            max_tokens=60
        )
    except Exception as e:
        return {"error": f"Error during query generation: {e}"}

    sql_query = response.choices[0].text.strip()  # este es el texto generado por GPT-4
    print(f"Generated SQL query: {sql_query}")

    # Ejecutar la consulta SQL
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        if sql_query.lower().startswith("select"):  # si es una instrucción SELECT
            rows = cursor.fetchall()
            print(f"Query results: {rows}")  # imprime los resultados
            return {"Query results": rows}  # retorna la consulta con los resultados
        conn.commit()  # hacer commit
    except Exception as e:
        conn.rollback()  # rollback en caso de error
        return {"error": f"Error during database query: {e}"}

    return {"message": "Query executed successfully"}

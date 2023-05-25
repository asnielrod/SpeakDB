import os
import psycopg2
import openai
from dotenv import load_dotenv
from fastapi import FastAPI
from openai import Completion
from typing import Optional

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




@app.get("/query/")
async def get_query(natural_language_query: Optional[str] = None):
    if natural_language_query is None:
        return {"error": "No query provided"}

    # Convertir la consulta en lenguaje natural a SQL usando GPT-4
    try:
        response = openai.Completion.create(
            engine=openai_model,
            prompt=f"Eres un asistente de inteligencia artificial diseñado para convertir consultas en lenguaje natural a consultas SQL para PostgreSQL. Aquí está tu tarea:\n{natural_language_query}\nSQL:",
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
        if sql_query.lower().startswith("select"):  # if it's a SELECT statement
            rows = cursor.fetchall()
            print(f"Query results: {rows}")  # print the query results
            return {"Query results": rows}  # return the query results
        conn.commit()  # commit the transaction
    except Exception as e:
        conn.rollback()  # rollback the transaction in case of error
        return {"error": f"Error during database query: {e}"}

    return {"message": "Query executed successfully"}

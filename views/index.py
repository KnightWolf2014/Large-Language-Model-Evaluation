import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime
from config.database import get_db_connection
import logging
import json

index_blueprint = Blueprint('index', __name__)

def get_unique_models():
    try:
        conn = get_db_connection()
        query = "SELECT DISTINCT json_each.value as model FROM chat, json_each(chat, '$.models')"
        models = conn.execute(query).fetchall()
        conn.close()
        return [model['model'] for model in models]
    except Exception as e:
        logging.error(f"Error al obtener modelos únicos: {e}")
        return []

@index_blueprint.route('/')
def index():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    model_name = request.args.get('model_name')
    models_list = get_unique_models()

    where_clauses = []
    parameters = []
    if start_date and end_date and start_time and end_time:
        try:
            start_datetime = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M')
            end_datetime = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M')
            where_clauses.append("c.created_at >= ? AND c.created_at  <= ?")
            parameters.extend([start_datetime.timestamp(), end_datetime.timestamp()])
        except ValueError:
            logging.warning("Formato de fecha/hora inválido en los parámetros de entrada.")
            return redirect(url_for('index'))

    if model_name:
        where_clauses.append("json_extract(c.chat, '$.models') LIKE ?")
        parameters.append(f"%{model_name}%")

    query = f"SELECT c.id, c.title, c.created_at, c.chat FROM chat c"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    try:
        conn = get_db_connection()
        chats = conn.execute(query, parameters).fetchall()
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Error al ejecutar la consulta SQL: {e}")
        chats = []

    processed_chats = [{
        'id': chat['id'],
        'title': chat['title'],
        'timestamp': datetime.fromtimestamp(int(chat['created_at'])).strftime('%Y-%m-%d %H:%M'),
        'models': ", ".join(json.loads(chat['chat']).get("models", []))
    } for chat in chats]

    return render_template('index.html', chats=processed_chats, models=models_list)

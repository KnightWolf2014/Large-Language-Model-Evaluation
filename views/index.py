import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime
from config.database import get_openwebui_db_connection
import logging
import json

index_blueprint = Blueprint('index', __name__)

def get_unique_models():
    try:
        conn = get_openwebui_db_connection()
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
    rating_filter = request.args.get('rating_filter') 
    comment_filter = request.args.get('comment_filter')

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    valid_per_page_values = [5, 10, 25]
    if per_page not in valid_per_page_values:
        per_page = 10

    models_list = get_unique_models()

    if start_date and not start_time:
        start_time = "00:00"

    if end_date and not end_time:
        end_time = "23:59"

    where_clauses = []
    parameters = []

    start_timestamp = None
    end_timestamp = None

    try:
        if start_date and start_time:
            start_datetime = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M')
            start_timestamp = start_datetime.timestamp()
    except ValueError:
        logging.warning("Formato de fecha/hora inválido en start_date/start_time.")

    try:
        if end_date and end_time:
            end_datetime = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M')
            end_timestamp = end_datetime.timestamp()
    except ValueError:
        logging.warning("Formato de fecha/hora inválido en end_date/end_time.")

    if start_timestamp and end_timestamp:
        where_clauses.append("c.created_at >= ? AND c.created_at <= ?")
        parameters.extend([start_timestamp, end_timestamp])
    elif start_timestamp:
        where_clauses.append("c.created_at >= ?")
        parameters.append(start_timestamp)
    elif end_timestamp:
        where_clauses.append("c.created_at <= ?")
        parameters.append(end_timestamp)

    # Filtrado por modelo
    if model_name:
        where_clauses.append("json_extract(c.chat, '$.models') LIKE ?")
        parameters.append(f"%{model_name}%")

    # Filtrado por rating y/o comentario en mensajes
    rating_condition = ""
    comment_condition = ""

    if rating_filter == 'positive':
        rating_condition = "json_extract(m.value, '$.annotation.rating') = 1"
    elif rating_filter == 'negative':
        rating_condition = "json_extract(m.value, '$.annotation.rating') = -1"
    elif rating_filter == 'none':
        rating_condition = "json_extract(m.value, '$.annotation.rating') IS NULL"

    if comment_filter == 'with':
        comment_condition = "(json_extract(m.value, '$.annotation.comment') IS NOT NULL AND json_extract(m.value, '$.annotation.comment') <> '')"
    elif comment_filter == 'without':
        comment_condition = "(json_extract(m.value, '$.annotation.comment') IS NULL OR json_extract(m.value, '$.annotation.comment') = '')"

    conditions_for_exists = []
    conditions_for_exists.append("json_extract(m.value, '$.role') = 'assistant'")

    if rating_condition:
        conditions_for_exists.append(rating_condition)
    if comment_condition:
        conditions_for_exists.append(comment_condition)

    if rating_filter or comment_filter:
        msg_filter = " AND ".join(conditions_for_exists)
        where_clauses.append(f"EXISTS (SELECT 1 FROM json_each(c.chat, '$.history.messages') AS m WHERE {msg_filter})")

    query = "SELECT c.id, c.title, c.created_at, c.chat FROM chat c ORDER BY c.created_at DESC"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    # Paginación
    count_query = f"SELECT COUNT(*) as total FROM ({query}) as sub"
    try:
        conn = get_openwebui_db_connection()
        total = conn.execute(count_query, parameters).fetchone()["total"]
    except sqlite3.Error as e:
        logging.error(f"Error al contar resultados: {e}")
        total = 0

    offset = (page - 1) * per_page
    query += " LIMIT ? OFFSET ?"
    parameters.extend([per_page, offset])

    try:
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

    total_pages = (total // per_page) + (1 if total % per_page != 0 else 0)

    args_dict = request.args.to_dict()

    prev_args = dict(args_dict)
    prev_args['page'] = page - 1

    next_args = dict(args_dict)
    next_args['page'] = page + 1

    return render_template('index.html',
                           chats=processed_chats,
                           models=models_list,
                           page=page,
                           per_page=per_page,
                           total=total,
                           total_pages=total_pages,
                           valid_per_page_values=valid_per_page_values,
                           prev_args=prev_args,
                           next_args=next_args)


from datetime import datetime
import sqlite3
import os
import json
import markdown
import logging
from flask import Flask, render_template, request, redirect, url_for
from flask_httpauth import HTTPBasicAuth

# Configuración de logging
logging.basicConfig(level=logging.INFO, filename='app.log', filemode='a',
                    format='%(name)s - %(levelname)s - %(message)s')

# Variables de entorno y configuración
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'llmentor')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'llmprimer')

DATABASE = os.getenv('DATABASE_PATH', '/app/backend/data/webui.db')
logging.info(f"Conectando a la base de datos en {DATABASE}")





# Inicializar aplicación y autenticación
app = Flask(__name__)
auth = HTTPBasicAuth()

# Usuarios para autenticación
users = {ADMIN_USERNAME: ADMIN_PASSWORD}



@auth.verify_password
def verify_password(username, password):
    if username in users and users[username] == password:
        return username
    return None

# Función de conexión a la base de datos
def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        logging.info("Conexión a la base de datos establecida.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        raise e

# Obtener modelos únicos
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

# Ruta de inicio
@app.route('/')
@auth.login_required
def index():
    # Obtener filtros de la solicitud
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    model_name = request.args.get('model_name')
    models_list = get_unique_models()

    # Construir consulta SQL basada en filtros
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



# Ruta de detalle del chat
@app.route('/chat/<id>')
@auth.login_required
def chat(id):
    try:
        conn = get_db_connection()

        # Obtener el registro de chat por ID
        chat_record = conn.execute('SELECT * FROM chat WHERE id = ?', (id,)).fetchone()

        # Obtener todo el mensaje (creo que no hace falta, pero puede servir)
        messages_query = '''
            SELECT
                json_extract(message.value, '$.id') AS message_id,
                json_extract(message.value, '$.role') AS role,
                json_extract(message.value, '$.content') AS content,
                json_extract(message.value, '$.timestamp') AS timestamp,
                json_extract(message.value, '$.annotation.rating') AS rating,
                json_extract(message.value, '$.annotation.comment') AS comment
            FROM chat,
                json_each(chat.chat, '$.history.messages') AS message
            WHERE chat.id = ?
        '''
        messages = conn.execute(messages_query, (id,)).fetchall()
        
        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Error al obtener el registro de chat con id {id}: {e}")
        return redirect(url_for('index'))

    # Procesar los mensajes obtenidos de la consulta
    messages_data = []
    for message in messages:
        
        message_data = {
            'id': message['message_id'],
            'role': message['role'],
            'content': markdown.markdown(message['content']) if message['content'] else '',
            'timestamp': message['timestamp'],
            'rating': message['rating'],
            'comment': message['comment']
        }
        
        messages_data.append(message_data)

    return render_template('chat.html', title=chat_record['title'], messages=messages_data, timestamp=chat_record['created_at'])

# Ejecutar aplicación
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")

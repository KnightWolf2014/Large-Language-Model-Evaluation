import sqlite3
from flask import Blueprint, render_template, redirect, url_for
from config.database import get_openwebui_db_connection
import markdown
import logging

chat_blueprint = Blueprint('chat', __name__)

@chat_blueprint.route('/chat/<id>')
def chat(id):
    try:
        conn = get_openwebui_db_connection()
        chat_record = conn.execute('SELECT * FROM chat WHERE id = ?', (id,)).fetchone()
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

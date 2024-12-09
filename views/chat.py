import sqlite3
from flask import Blueprint, render_template, redirect, url_for, request
from config.database import get_openwebui_db_connection
import markdown
import logging
from datetime import datetime

chat_blueprint = Blueprint('chat', __name__)

@chat_blueprint.route('/chat/<id>')
def chat(id):
    try:
        conn = get_openwebui_db_connection()
        chat_record = conn.execute('SELECT * FROM chat WHERE id = ?', (id,)).fetchone()
        messages_query = '''
            SELECT
                json_extract(message.value, '$.id') AS message_id,
                json_extract(message.value, '$.parentId') AS parent_id,
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
        return redirect(url_for('index.index'))

    # Convertir a diccionarios
    msg_dict = {}
    for m in messages:
        msg_id = m['message_id']
        raw_content = m['content'] if m['content'] else ''
        display_content = markdown.markdown(raw_content)
        msg_dict[msg_id] = {
            'id': msg_id,
            'parent_id': m['parent_id'],
            'role': m['role'],
            'raw_content': raw_content,
            'display_content': display_content,
            'timestamp': m['timestamp'],
            'rating': m['rating'],
            'comment': m['comment']
        }

    # Crear pares prompt/response
    pairs = []
    for m in msg_dict.values():
        if m['role'] == 'user':
            user_msg = m
            for candidate in msg_dict.values():
                if candidate['parent_id'] == user_msg['id'] and candidate['role'] == 'assistant':
                    pairs.append({
                        'prompt_raw': user_msg['raw_content'],
                        'prompt_display': user_msg['display_content'],
                        'prompt_timestamp': user_msg['timestamp'],
                        'response_raw': candidate['raw_content'],
                        'response_display': candidate['display_content'],
                        'response_timestamp': candidate['timestamp'],
                        'rating': candidate['rating'],
                        'comment': candidate['comment']
                    })

    chat_timestamp_formatted = datetime.fromtimestamp(int(chat_record['created_at'])).strftime('%Y-%m-%d %H:%M')

    return render_template('chat.html', title=chat_record['title'], pairs=pairs, timestamp=chat_timestamp_formatted)

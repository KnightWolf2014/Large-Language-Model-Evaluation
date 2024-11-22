import sys
from flask import Blueprint, jsonify, render_template
import sqlite3
from config.database import get_openwebui_db_connection, get_project_db_connection

# Crear el Blueprint para el banco de pruebas
testbank_blueprint = Blueprint('testbank', __name__)

# Función para sincronizar respuestas positivas desde OpenWebUI al banco de pruebas
@testbank_blueprint.route('/testbank/sync', methods=['POST'])
def sync_positives():
    try:
        # Conexión a ambas bases de datos
        openwebui_conn = get_openwebui_db_connection()
        project_conn = get_project_db_connection()

        # Consulta para extraer mensajes con rating positivo y sus prompts
        query = '''
            SELECT 
                json_extract(message.value, '$.id') AS response_id,
                json_extract(chat.chat, '$.title') AS title,
                json_extract(message.value, '$.content') AS response,
                (
                    SELECT json_extract(parent_message.value, '$.content')
                    FROM json_each(chat.chat, '$.history.messages') AS parent_message
                    WHERE json_extract(parent_message.value, '$.id') = 
                          json_extract(message.value, '$.parentId')
                ) AS prompt,
                json_extract(message.value, '$.annotation.comment') AS comment
            FROM chat, json_each(chat.chat, '$.history.messages') AS message
            WHERE json_extract(message.value, '$.annotation.rating') = 1
        '''
        positives = openwebui_conn.execute(query).fetchall()

        # Log de la cantidad de mensajes positivos obtenidos
        print(f"Respuestas positivas encontradas: {len(positives)}")

        # Insertarlas en la base de datos del proyecto
        insert_query = '''
        INSERT INTO positive_responses (id, title, prompt, response, comment)
        VALUES (?, ?, ?, ?, ?)
        '''
        for row in positives:
            try:
                response_id = row[0]
                title = row[1]
                prompt = row[3]  # Asegurarse de tomar el campo prompt
                response = row[2]
                comment = row[4]

                # Log para depuración
                print(f"\n--- Sincronizando entrada ---")
                print(f"ID: {response_id}")
                print(f"Título: {title}")
                print(f"Prompt: {prompt}")
                print(f"Respuesta: {response}")
                print(f"Comentario: {comment}\n")

                # Insertar en la tabla
                project_conn.execute(insert_query, (response_id, title, prompt, response, comment))
                print(f"Insertada respuesta positiva con ID: {response_id}")
            except sqlite3.Error as e:
                print(f"Error al insertar la respuesta positiva con ID {response_id}: {str(e)}")

        # Confirmar cambios
        project_conn.commit()
        print("Cambios confirmados en la base de datos del proyecto.")

        sys.stdout.flush()

        # Cerrar conexiones
        openwebui_conn.close()
        project_conn.close()

        return jsonify({'message': 'Respuestas positivas sincronizadas exitosamente.'})

    except sqlite3.Error as e:
        return jsonify({'error': f"Error al sincronizar datos: {str(e)}"}), 500


# Ruta para listar las respuestas positivas desde el banco de pruebas
@testbank_blueprint.route('/testbank/positives', methods=['GET'])
def list_positives():
    try:
        conn = get_project_db_connection()
        query = """
        SELECT id, title, prompt, response, comment
        FROM positive_responses
        """
        results = conn.execute(query).fetchall()
        conn.close()

        # Formatear las respuestas
        positives = [
            {
                'id': row[0],
                'title': row[1],
                'prompt': row[2],
                'response': row[3],
                'comment': row[4]
            }
            for row in results
        ]

        # Log de depuración
        print(f"Listado de respuestas positivas: {len(positives)} entradas encontradas.")
        for positive in positives:
            print(f"ID: {positive['id']}, Título: {positive['title']}")

        # Renderizar la lista con un HTML o devolver JSON
        return render_template('positives.html', responses=positives)

    except sqlite3.Error as e:
        return jsonify({'error': f"Error al obtener datos: {str(e)}"}), 500

import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from config.database import get_project_db_connection
from flask import Response
import json

datasets_blueprint = Blueprint('datasets', __name__)

@datasets_blueprint.route('/datasets', methods=['GET'])
def list_datasets():
    conn = get_project_db_connection()
    query = "SELECT id, title, name, description FROM datasets"
    results = conn.execute(query).fetchall()
    conn.close()

    datasets = [
        {
            'id': row['id'],
            'title': row['title'],
            'name': row['name'],
            'description': row['description']
        }
        for row in results
    ]

    return render_template('datasets.html', datasets=datasets)

@datasets_blueprint.route('/datasets/create', methods=['POST'])
def create_dataset():
    title = request.form.get('title')
    name = request.form.get('name')
    description = request.form.get('description')
    if not title or not name:
        return jsonify({'error': 'Title and Name are required'}), 400

    conn = get_project_db_connection()
    try:
        conn.execute("INSERT INTO datasets (title, name, description) VALUES (?, ?, ?)", (title, name, description))
        conn.commit()
    except sqlite3.IntegrityError:
        # El name debe ser único
        return jsonify({'error': 'Dataset name must be unique'}), 400
    finally:
        conn.close()

    return redirect(url_for('datasets.list_datasets'))

@datasets_blueprint.route('/datasets/<int:dataset_id>/edit', methods=['POST'])
def edit_dataset(dataset_id):
    title = request.form.get('title')
    name = request.form.get('name')
    description = request.form.get('description')
    if not title or not name:
        return jsonify({'error': 'Title and Name are required'}), 400

    conn = get_project_db_connection()
    try:
        conn.execute("UPDATE datasets SET title = ?, name = ?, description = ? WHERE id = ?", (title, name, description, dataset_id))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Dataset name must be unique'}), 400
    finally:
        conn.close()

    return redirect(url_for('datasets.list_datasets'))

@datasets_blueprint.route('/datasets/<int:dataset_id>/delete', methods=['POST'])
def delete_dataset(dataset_id):
    conn = get_project_db_connection()
    conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('datasets.list_datasets'))

# Ruta para ver las respuestas de un dataset
@datasets_blueprint.route('/datasets/<int:dataset_id>/responses', methods=['GET'])
def list_dataset_responses(dataset_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    valid_per_page_values = [5,10,25]
    if per_page not in valid_per_page_values:
        per_page = 10

    conn = get_project_db_connection()

    # Obtener info del dataset actual
    ds_row = conn.execute("SELECT title, name FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    if not ds_row:
        conn.close()
        return "Dataset not found", 404

    count_query = "SELECT COUNT(*) as total FROM dataset_responses WHERE dataset_id = ?"
    total = conn.execute(count_query, (dataset_id,)).fetchone()['total']

    offset = (page - 1) * per_page
    query = "SELECT id, prompt, response, comment FROM dataset_responses WHERE dataset_id = ? LIMIT ? OFFSET ?"
    responses = conn.execute(query, (dataset_id, per_page, offset)).fetchall()

    conn.close()

    responses_data = [
        {
            'id': row['id'],
            'prompt': row['prompt'],
            'response': row['response'],
            'comment': row['comment']
        }
        for row in responses
    ]

    total_pages = (total // per_page) + (1 if total % per_page != 0 else 0)

    args_dict = request.args.to_dict()
    prev_args = dict(args_dict)
    prev_args['page'] = page - 1
    next_args = dict(args_dict)
    next_args['page'] = page + 1

    dataset = {
        'title': ds_row['title'],
        'name': ds_row['name']
    }

    return render_template('databank.html',
                           responses=responses_data,
                           dataset_id=dataset_id,
                           dataset=dataset,
                           page=page,
                           per_page=per_page,
                           total=total,
                           total_pages=total_pages,
                           valid_per_page_values=valid_per_page_values,
                           prev_args=prev_args,
                           next_args=next_args)



# Endpoints para las acciones en dataset_responses (editar, duplicar, borrar)
@datasets_blueprint.route('/datasets/<int:dataset_id>/responses/<int:response_id>/delete', methods=['POST'])
def delete_dataset_response(dataset_id, response_id):
    conn = get_project_db_connection()
    conn.execute("DELETE FROM dataset_responses WHERE id = ? AND dataset_id = ?", (response_id, dataset_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted successfully'})

@datasets_blueprint.route('/datasets/<int:dataset_id>/responses/<int:response_id>/update', methods=['POST'])
def update_dataset_response(dataset_id, response_id):
    prompt = request.form.get('prompt')
    response = request.form.get('response')
    comment = request.form.get('comment')

    conn = get_project_db_connection()
    conn.execute("UPDATE dataset_responses SET prompt = ?, response = ?, comment = ? WHERE id = ? AND dataset_id = ?", (prompt, response, comment, response_id, dataset_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Updated successfully'})

@datasets_blueprint.route('/datasets/<int:dataset_id>/responses/<int:response_id>/duplicate', methods=['POST'])
def duplicate_dataset_response(dataset_id, response_id):
    conn = get_project_db_connection()
    row = conn.execute("SELECT prompt, response, comment FROM dataset_responses WHERE id = ? AND dataset_id = ?", (response_id, dataset_id)).fetchone()
    if row:
        conn.execute("INSERT INTO dataset_responses (dataset_id, prompt, response, comment) VALUES (?, ?, ?, ?)", (dataset_id, row['prompt'], row['response'], row['comment']))
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({
            'message': 'Duplicated successfully',
            'entry': {
                'id': new_id,
                'prompt': row['prompt'],
                'response': row['response'],
                'comment': row['comment']
            }
        }), 200
    conn.close()
    return jsonify({'message': 'Entry not found'}), 404


@datasets_blueprint.route('/datasets/<int:dataset_id>/download', methods=['GET'])
def download_dataset(dataset_id):
    conn = get_project_db_connection()
    ds_row = conn.execute("SELECT name FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    if not ds_row:
        conn.close()
        return "Dataset not found", 404
    
    dataset_name = ds_row['name']

    query = "SELECT prompt, response, comment FROM dataset_responses WHERE dataset_id = ?"
    results = conn.execute(query, (dataset_id,)).fetchall()
    conn.close()

    data = [
        {
            "prompt": row['prompt'],
            "response": {
                "model_response": row['response'],
                "comment": row['comment'] if row['comment'] else ""
            }
        } for row in results
    ]

    response = Response(
        response=json.dumps(data, indent=4, ensure_ascii=False),
        mimetype='application/json'
    )
    # Usar el nombre del dataset para el archivo
    filename = f"{dataset_name}.json"
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response



@datasets_blueprint.route('/datasets/json', methods=['GET'])
def list_datasets_json():
    conn = get_project_db_connection()
    query = "SELECT id, title, name, description FROM datasets"
    results = conn.execute(query).fetchall()
    conn.close()

    datasets = [
        {
            'id': row['id'],
            'title': row['title'],
            'name': row['name'],
            'description': row['description']
        }
        for row in results
    ]
    return jsonify(datasets)
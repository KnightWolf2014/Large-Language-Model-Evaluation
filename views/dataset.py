import sys
from flask import Blueprint, json, jsonify, render_template, Response, request
import sqlite3
from config.database import get_project_db_connection

dataset_blueprint = Blueprint('dataset', __name__)


# Función para mostrar un dataset especifico
@dataset_blueprint.route('/dataset/<int:dataset_id>/responses', methods=['GET'])
def list_dataset_responses(dataset_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    valid_per_page_values = [5, 10, 25]
    if per_page not in valid_per_page_values:
        per_page = 10

    conn = get_project_db_connection()

    ds_row = conn.execute("SELECT title, name FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    if not ds_row:
        conn.close()
        return "Dataset not found", 404

    count_query = "SELECT COUNT(*) as total FROM dataset_responses WHERE dataset_id = ?"
    total = conn.execute(count_query, (dataset_id,)).fetchone()['total']

    offset = (page - 1) * per_page
    query = "SELECT id, prompt, response, comment, rating FROM dataset_responses WHERE dataset_id = ? LIMIT ? OFFSET ?"
    responses = conn.execute(query, (dataset_id, per_page, offset)).fetchall()
    conn.close()

    responses_data = []
    for row in responses:
        rating_val = row['rating'] if row['rating'] is not None else 0
        responses_data.append({
            'id': row['id'],
            'prompt': row['prompt'],
            'response': row['response'],
            'comment': row['comment'],
            'rating': rating_val
        })

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

    return render_template('dataset.html',
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


# Función para descargar un dataset en formato JSON
@dataset_blueprint.route('/dataset/<int:dataset_id>/download', methods=['GET'])
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

    filename = f"{dataset_name}.json"
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# Función para editar una entrada de un dataset
@dataset_blueprint.route('/dataset/<int:dataset_id>/responses/<int:response_id>/update', methods=['POST'])
def update_dataset_response(dataset_id, response_id):
    prompt = request.form.get('prompt')
    response = request.form.get('response')
    comment = request.form.get('comment')
    rating_str = request.form.get('rating')

    if rating_str == '1':
        rating_val = 1
    elif rating_str == '-1':
        rating_val = -1
    else:
        rating_val = None

    conn = get_project_db_connection()
    conn.execute("UPDATE dataset_responses SET prompt = ?, response = ?, comment = ?, rating = ? WHERE id = ? AND dataset_id = ?",
                 (prompt, response, comment, rating_val, response_id, dataset_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Updated successfully'})


# Función para borrar una entrada de un dataset
@dataset_blueprint.route('/dataset/<int:dataset_id>/responses/<int:response_id>/delete', methods=['POST'])
def delete_dataset_response(dataset_id, response_id):
    conn = get_project_db_connection()
    conn.execute("DELETE FROM dataset_responses WHERE id = ? AND dataset_id = ?", (response_id, dataset_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted successfully'})


# Función para duplicar una entrada de un dataset
@dataset_blueprint.route('/dataset/<int:dataset_id>/responses/<int:response_id>/duplicate', methods=['POST'])
def duplicate_dataset_response(dataset_id, response_id):
    conn = get_project_db_connection()
    row = conn.execute("SELECT prompt, response, comment, rating FROM dataset_responses WHERE id = ? AND dataset_id = ?", (response_id, dataset_id)).fetchone()
    if row:
        conn.execute("INSERT INTO dataset_responses (dataset_id, prompt, response, comment, rating) VALUES (?, ?, ?, ?, ?)",
                     (dataset_id, row['prompt'], row['response'], row['comment'], row['rating']))
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        rating_val = row['rating'] if row['rating'] is not None else 0
        return jsonify({
            'message': 'Duplicated successfully',
            'entry': {
                'id': new_id,
                'prompt': row['prompt'],
                'response': row['response'],
                'comment': row['comment'],
                'rating': rating_val
            }
        }), 200
    conn.close()
    return jsonify({'message': 'Entry not found'}), 404


# Función para guardar las entradas que queramos de un chat en un dataset
@dataset_blueprint.route('/dataset/save_selected', methods=['POST'])
def save_selected():
    selected = request.form.getlist('selected')
    dataset_ids = request.form.getlist('dataset_ids')
    if not selected or not dataset_ids:
        return jsonify({'message': 'No selections made or no datasets chosen'}), 400

    pairs_count_str = request.form.get('pairs_count', '0')
    try:
        pairs_count = int(pairs_count_str)
    except ValueError:
        pairs_count = 0

    all_pairs = []
    for i in range(pairs_count):
        prompt = request.form.get(f'prompt_{i}', '')
        response = request.form.get(f'response_{i}', '')
        comment = request.form.get(f'comment_{i}', '')
        rating_val_str = request.form.get(f'rating_{i}', '0')
        try:
            rating_val = int(rating_val_str)
        except ValueError:
            rating_val = 0
        all_pairs.append({
            'prompt': prompt,
            'response': response,
            'comment': comment,
            'rating': rating_val
        })

    selected_indices = [int(x) for x in selected]

    max_rating_line = -1
    for idx in selected_indices:
        if all_pairs[idx]['rating'] in (1, -1):
            if idx > max_rating_line:
                max_rating_line = idx

    conn = get_project_db_connection()
    insert_query = "INSERT INTO dataset_responses (dataset_id, prompt, response, comment, rating) VALUES (?, ?, ?, ?, ?)"

    if max_rating_line >= 0:
        for d_id in dataset_ids:
            for i in range(max_rating_line + 1):
                p = all_pairs[i]
                conn.execute(insert_query, (d_id, p['prompt'], p['response'], p['comment'], p['rating']))
    else:
        for d_id in dataset_ids:
            for idx in selected_indices:
                p = all_pairs[idx]
                conn.execute(insert_query, (d_id, p['prompt'], p['response'], p['comment'], p['rating']))

    conn.commit()
    conn.close()

    return jsonify({'message': 'Selected responses saved successfully.'})

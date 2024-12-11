import sys
from flask import Blueprint, json, jsonify, render_template, Response, request
import sqlite3
from config.database import get_project_db_connection

testbank_blueprint = Blueprint('testbank', __name__)

@testbank_blueprint.route('/testbank/list_dataset', methods=['GET'])
def list_dataset():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    valid_per_page_values = [5, 10, 25]
    if per_page not in valid_per_page_values:
        per_page = 10

    try:
        conn = get_project_db_connection()
        count_query = "SELECT COUNT(*) as total FROM dataset_responses"
        total = conn.execute(count_query).fetchone()["total"]

        offset = (page - 1) * per_page
        query = "SELECT id, prompt, response, comment FROM dataset_responses LIMIT ? OFFSET ?"
        results = conn.execute(query, (per_page, offset)).fetchall()
        conn.close()

        dataset = [
            {
                'id': row[0],
                'prompt': row[1],
                'response': row[2],
                'comment': row[3]
            }
            for row in results
        ]

        total_pages = (total // per_page) + (1 if total % per_page != 0 else 0)

        args_dict = request.args.to_dict()
        prev_args = dict(args_dict)
        next_args = dict(args_dict)
        
        prev_args['page'] = page - 1
        next_args['page'] = page + 1

        return render_template('databank.html', 
                               responses=dataset,
                               page=page,
                               per_page=per_page,
                               total=total,
                               total_pages=total_pages,
                               valid_per_page_values=valid_per_page_values,
                               prev_args=prev_args,
                               next_args=next_args)
    except sqlite3.Error as e:
        return jsonify({'error': f"Error obtaining dataset: {str(e)}"}), 500


@testbank_blueprint.route('/testbank/download_dataset', methods=['GET'])
def download_dataset_json():
    try:
        conn = get_project_db_connection()
        query = "SELECT prompt, response, comment FROM dataset_responses"
        results = conn.execute(query).fetchall()
        conn.close()

        # Crear el JSON
        data_entries = [
            {
                "prompt": row[0],
                "response": {
                    "model_response": row[1],
                    "comment": row[2] if row[2] else ""
                }
            }
            for row in results
        ]

        response = Response(
            response=json.dumps(data_entries, indent=4, ensure_ascii=False),
            mimetype='application/json'
        )
        response.headers['Content-Disposition'] = 'attachment; filename=DataBank.json'
        return response

    except sqlite3.Error as e:
        return jsonify({'error': f"Error al obtener datos: {str(e)}"}), 500


@testbank_blueprint.route('/testbank/edit/<id>', methods=['POST'])
def edit_entry(id):
    prompt = request.form.get('prompt', '')
    response = request.form.get('response', '')
    comment = request.form.get('comment', '')

    try:
        conn = get_project_db_connection()
        conn.execute("UPDATE dataset_responses SET prompt=?, response=?, comment=? WHERE id = ?", (prompt, response, comment, id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Entry edited successfully.'}), 200
    except sqlite3.Error as e:
        return jsonify({'message': f'Error editing entry: {str(e)}'}), 500


@testbank_blueprint.route('/testbank/delete/<id>', methods=['POST'])
def delete_entry(id):
    try:
        conn = get_project_db_connection()
        conn.execute("DELETE FROM dataset_responses WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Entry deleted successfully.'}), 200
    except sqlite3.Error as e:
        return jsonify({'message': f'Error deleting entry: {str(e)}'}), 500


@testbank_blueprint.route('/testbank/duplicate/<id>', methods=['POST'])
def duplicate_entry(id):
    try:
        conn = get_project_db_connection()
        row = conn.execute("SELECT prompt, response, comment FROM dataset_responses WHERE id = ?", (id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'message': 'Entry not found'}), 404
        prompt, response, comment = row
        conn.execute("INSERT INTO dataset_responses (prompt, response, comment) VALUES (?, ?, ?)", (prompt, response, comment))
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({
            'message': 'Entry duplicated successfully.',
            'entry': {
                'id': new_id,
                'prompt': prompt,
                'response': response,
                'comment': comment
            }
        }), 200
    except sqlite3.Error as e:
        return jsonify({'message': f'Error duplicating entry: {str(e)}'}), 500


@testbank_blueprint.route('/testbank/save_selected', methods=['POST'])
def save_selected():
    selected = request.form.getlist('selected')
    dataset_ids = request.form.getlist('dataset_ids')
    if not selected or not dataset_ids:
        return jsonify({'message': 'No selections made or no datasets chosen'}), 400

    conn = get_project_db_connection()
    insert_query = "INSERT INTO dataset_responses (dataset_id, prompt, response, comment) VALUES (?, ?, ?, ?)"

    for idx in selected:
        prompt = request.form.get(f'prompt_{idx}', '')
        response = request.form.get(f'response_{idx}', '')
        comment = request.form.get(f'comment_{idx}', '')
        for d_id in dataset_ids:
            conn.execute(insert_query, (d_id, prompt, response, comment))

    conn.commit()
    conn.close()

    return jsonify({'message': 'Selected responses saved successfully.'})





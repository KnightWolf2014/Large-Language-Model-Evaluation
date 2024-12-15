import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from config.database import get_project_db_connection
from flask import Response
import json

datasets_blueprint = Blueprint('datasets', __name__)


# Función para mostrar todos los datasets que tengamos creados
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


# Función para crear un dataset
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
        return jsonify({'error': 'Dataset name must be unique'}), 400
    finally:
        conn.close()

    return redirect(url_for('datasets.list_datasets'))


# Función para editar un dataset
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


# Función para borrar un dataset
@datasets_blueprint.route('/datasets/<int:dataset_id>/delete', methods=['POST'])
def delete_dataset(dataset_id):
    conn = get_project_db_connection()
    conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('datasets.list_datasets'))


# Función para mostrar el modal a la hora de guardar un conjunto de entradas
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

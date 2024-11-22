import sqlite3
import logging
from .config import DATABASE_OPENWEBUI_PATH, DATABASE_PROJECT_PATH

def get_openwebui_db_connection():
    """Conecta con la base de datos de OpenWebUI."""
    try:
        conn = sqlite3.connect(DATABASE_OPENWEBUI_PATH)
        conn.row_factory = sqlite3.Row
        logging.info("Conexión a la base de datos de OpenWebUI establecida.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Error al conectar a la base de datos de OpenWebUI: {e}")
        raise e

def get_project_db_connection():
    """Conecta con la base de datos del proyecto (para almacenar respuestas del banco de pruebas)."""
    try:
        conn = sqlite3.connect(DATABASE_PROJECT_PATH)
        conn.row_factory = sqlite3.Row
        logging.info("Conexión a la base de datos del proyecto establecida.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Error al conectar a la base de datos del proyecto: {e}")
        raise e

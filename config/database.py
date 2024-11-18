import sqlite3
import logging
from .config import DATABASE_PATH

def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        logging.info("Conexión a la base de datos establecida.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        raise e

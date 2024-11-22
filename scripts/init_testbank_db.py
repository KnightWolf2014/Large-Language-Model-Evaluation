import sqlite3
from config.config import DATABASE_PROJECT_PATH

def create_positive_responses_table():
    try:
        conn = sqlite3.connect(DATABASE_PROJECT_PATH)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS positive_responses (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            comment TEXT
        )
        """)

        conn.commit()
        print("Tabla 'positive_responses' creada o verificada exitosamente.")

    except sqlite3.Error as e:
        print(f"Error al crear la tabla 'positive_responses': {e}")

    finally:
        if conn:
            conn.close()

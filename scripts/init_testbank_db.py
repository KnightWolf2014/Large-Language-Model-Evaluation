import sqlite3
from config.config import DATABASE_PROJECT_PATH

def create_dataset_responses_table():
    try:
        conn = sqlite3.connect(DATABASE_PROJECT_PATH)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dataset_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            comment TEXT
        )
        """)

        conn.commit()
        print("Tabla 'dataset_responses' creada o verificada exitosamente.")

    except sqlite3.Error as e:
        print(f"Error al crear la tabla 'dataset_responses': {e}")

    finally:
        if conn:
            conn.close()

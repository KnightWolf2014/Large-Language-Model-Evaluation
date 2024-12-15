import sqlite3
from config.config import DATABASE_PROJECT_PATH

def create_dataset_responses_table():
    try:
        conn = sqlite3.connect(DATABASE_PROJECT_PATH)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dataset_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            rating INTEGER,
            comment TEXT,
            FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
        );
        """)

        conn.commit()
        print("Tabla 'dataset_responses' creada o verificada exitosamente.")

    except sqlite3.Error as e:
        print(f"Error al crear la tabla 'dataset_responses': {e}")

    finally:
        if conn:
            conn.close()


def create_datasets_table():
    try:
        conn = sqlite3.connect(DATABASE_PROJECT_PATH)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        );
        """)

        conn.commit()
        print("Tabla 'datasets' creada o verificada exitosamente.")

    except sqlite3.Error as e:
        print(f"Error al crear la tabla 'datasets': {e}")

    finally:
        if conn:
            conn.close()
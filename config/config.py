import os
import logging
from flask import Flask
from flask_httpauth import HTTPBasicAuth

# Configuración de logging
logging.basicConfig(level=logging.INFO, filename='app.log', filemode='a',
                    format='%(name)s - %(levelname)s - %(message)s')

# Inicializar aplicación Flask
app = Flask(__name__)

# Configuración de autenticación
auth = HTTPBasicAuth()

# Variables de entorno y configuración
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'llmentor')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'llmprimer')

DATABASE_OPENWEBUI_PATH = os.getenv('DATABASE_OPENWEBUI_PATH', '/app/backend/data/webui.db')
DATABASE_PROJECT_PATH = os.getenv('DATABASE_PROJECT_PATH', '/app/data/webui.db')

# Usuarios para autenticación
USERS = {ADMIN_USERNAME: ADMIN_PASSWORD}

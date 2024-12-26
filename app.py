from flask import Flask
from flask_cors import CORS

from config.config import app
from config.auth import auth

from scripts.init_database import create_dataset_responses_table, create_datasets_table

from views.index import index_blueprint
from views.chat import chat_blueprint 
from views.dataset import dataset_blueprint
from views.loadModel import loadModel_blueprint
from views.datasets import datasets_blueprint
from views.evaluateResults import evaluateResults_blueprint

app = Flask(__name__, template_folder='templates')
app.secret_key = 'ClaveDeSeguridadTFG'

CORS(app)

app.register_blueprint(index_blueprint)
app.register_blueprint(chat_blueprint)
app.register_blueprint(dataset_blueprint)
app.register_blueprint(loadModel_blueprint)
app.register_blueprint(datasets_blueprint)
app.register_blueprint(evaluateResults_blueprint)

create_dataset_responses_table()
create_datasets_table()

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")

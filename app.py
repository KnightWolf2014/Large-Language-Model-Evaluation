from flask import Flask
from config.config import app
from views.index import index_blueprint
from views.chat import chat_blueprint 
from config.auth import auth

app = Flask(__name__, template_folder='templates')

app.register_blueprint(index_blueprint)
app.register_blueprint(chat_blueprint)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")

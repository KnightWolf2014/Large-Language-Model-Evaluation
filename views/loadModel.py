import sys
import json
import time
import uuid
from flask import Blueprint, jsonify, render_template, request
import urllib.request


loadModel_blueprint = Blueprint('loadModel', __name__)


# Función para obtener el token de autenticación
def get_auth_token(server_url, username, password):
    auth_url = f"{server_url}/api/v1/auths/signin"
    payload = json.dumps({"email": username, "password": password}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    try:
        request_obj = urllib.request.Request(auth_url, data=payload, headers=headers)
        with urllib.request.urlopen(request_obj) as response:
            if response.status == 200:
                auth_data = json.load(response)
                return auth_data.get("token")
            else:
                print(f"Error al autenticar: {response.read().decode('utf-8')}")
                return None
    except urllib.error.HTTPError as e:
        print(f"HTTPError en autenticación: {e.read().decode('utf-8')}")
        return None
    except urllib.error.URLError as e:
        print(f"URLError en autenticación: {str(e)}")
        return None


# Función para mostrar la UI
@loadModel_blueprint.route('/loadModel', methods=['GET'])
def load_model():
    return render_template('loadModel.html')


# Función para ejecutar el banco de pruebas
@loadModel_blueprint.route('/runTestBank', methods=['POST'])
def run_test_bank():
    try:
        server_url = request.form.get('server-url')
        model = request.form.get('model')
        username = request.form.get('username')
        password = request.form.get('password')
        file = request.files.get('testbank-json')

        if not (server_url and model and file and username and password):
            return jsonify({"error": "Faltan campos obligatorios"}), 400

        token = get_auth_token(server_url, username, password)
        if not token:
            return jsonify({"error": "No se pudo autenticar al servidor"}), 401

        prompts_json = json.load(file)
        prompts_only = [{"prompt": item["prompt"]} for item in prompts_json if "prompt" in item]

        if not prompts_only:
            return jsonify({"error": "El archivo JSON no contiene prompts válidos"}), 400

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        results = []

        # Procesamos cada prompt del test bank
        for p in prompts_only:
            user_msg_id = str(uuid.uuid4())
            initial_payload = json.dumps({
                "chat": {
                    "id": "",
                    "title": "Nuevo Chat",
                    "models": [model],
                    "params": {},
                    "messages": [{
                        "id": user_msg_id,
                        "parentId": None,
                        "childrenIds": [],
                        "role": "user",
                        "content": p["prompt"],
                        "timestamp": int(time.time() * 1000)
                    }]
                }
            }).encode("utf-8")

            try:
                req_new_chat = urllib.request.Request(f"{server_url}/api/v1/chats/new", data=initial_payload, headers=headers)
                with urllib.request.urlopen(req_new_chat) as response:
                    if response.status == 200:
                        chat_data = json.load(response)
                        chat_id = chat_data.get("id")
                        if not chat_id:
                            results.append({"prompt": p["prompt"], "response": "Error: no se pudo obtener chat_id."})
                            continue

                        session_id = str(uuid.uuid4())
                        assistant_msg_id = str(uuid.uuid4())
                        stream_payload = json.dumps({
                            "stream": True,
                            "model": model,
                            "messages": [{"role": "user", "content": p["prompt"]}],
                            "options": {},
                            "session_id": session_id,
                            "chat_id": chat_id,
                            "id": assistant_msg_id
                        }).encode("utf-8")

                        stream_req = urllib.request.Request(
                            f"{server_url}/ollama/api/chat",
                            data=stream_payload,
                            headers=headers,
                            method="POST"
                        )

                        assistant_content = ""

                        try:
                            with urllib.request.urlopen(stream_req) as stream_res:
                                for line in stream_res:
                                    line = line.strip()
                                    if line:
                                        chunk = json.loads(line)
                                        if "message" in chunk and "content" in chunk["message"]:
                                            assistant_content += chunk["message"]["content"]

                            results.append({"prompt": p["prompt"], "response": assistant_content})

                            delete_payload = json.dumps({"force": True}).encode("utf-8")
                            delete_req = urllib.request.Request(
                                f"{server_url}/api/v1/chats/{chat_id}",
                                data=delete_payload,
                                headers=headers,
                                method="DELETE"
                            )
                            try:
                                with urllib.request.urlopen(delete_req) as delete_res:
                                    if delete_res.status == 200:
                                        print(f"Chat {chat_id} borrado con éxito")
                                    else:
                                        print(f"Error borrando el chat {chat_id}: {delete_res.read().decode('utf-8')}")
                            except Exception as e_del:
                                print(f"No se pudo borrar el chat {chat_id}: {e_del}")

                        except Exception as e_stream:
                            results.append({"prompt": p["prompt"], "response": f"Error en el streaming: {str(e_stream)}"})

                    else:
                        details = response.read().decode("utf-8")
                        results.append({"prompt": p["prompt"], "response": f"Error al inicializar el chat: {details}"})
            except urllib.error.HTTPError as e_http:
                details = e_http.read().decode("utf-8")
                results.append({"prompt": p["prompt"], "response": f"HTTPError: {details}"})
            except urllib.error.URLError as e_url:
                results.append({"prompt": p["prompt"], "response": f"URLError: {str(e_url)}"})
            except Exception as e_general:
                results.append({"prompt": p["prompt"], "response": f"Excepción general: {str(e_general)}"})

        return render_template('testbank_results.html', results=results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
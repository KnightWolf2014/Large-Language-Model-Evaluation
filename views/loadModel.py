import sys
import json
import time
import uuid
from flask import Blueprint, jsonify, render_template, request, session
import urllib.request

loadModel_blueprint = Blueprint('loadModel', __name__)

def get_auth_token(server_url, username, password):
    auth_url = f"{server_url}/api/v1/auths/signin"
    payload = json.dumps({"email": username, "password": password}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    try:
        req = urllib.request.Request(auth_url, data=payload, headers=headers)
        with urllib.request.urlopen(req) as resp:
            if resp.status == 200:
                auth_data = json.load(resp)
                return auth_data.get("token")
            else:
                print(f"Error al autenticar: {resp.read().decode('utf-8')}")
                return None
    except urllib.error.HTTPError as e:
        print(f"HTTPError en autenticación: {e.read().decode('utf-8')}")
        return None
    except urllib.error.URLError as e:
        print(f"URLError en autenticación: {str(e)}")
        return None

@loadModel_blueprint.route('/loadModel', methods=['GET'])
def load_model():
    return render_template('loadModel.html')

@loadModel_blueprint.route('/runDataset', methods=['POST'])
def run_dataset():
    try:
        server_url = request.form.get('server-url')
        model = request.form.get('model')
        username = request.form.get('username')
        password = request.form.get('password')
        file = request.files.get('dataset-json')

        if not (server_url and model and file and username and password):
            return jsonify({"error": "Faltan campos obligatorios"}), 400

        token = get_auth_token(server_url, username, password)
        if not token:
            return jsonify({"error": "No se pudo autenticar al servidor"}), 401

        prompts_json = json.load(file)
        processed_items = []
        for item in prompts_json:
            if ("prompt" in item and
                "response" in item and
                isinstance(item["response"], dict) and
                "model_response" in item["response"]):
                processed_items.append({
                    "prompt": item["prompt"],
                    "expected_response": item["response"]["model_response"]
                })

        if not processed_items:
            return jsonify({"error": "El JSON no contiene prompts con response->model_response"}), 400

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        results = []

        first_prompt = processed_items[0]["prompt"]
        first_expected = processed_items[0]["expected_response"]
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
                    "content": first_prompt,
                    "timestamp": int(time.time() * 1000)
                }]
            }
        }).encode("utf-8")

        try:
            req_new_chat = urllib.request.Request(
                f"{server_url}/api/v1/chats/new",
                data=initial_payload,
                headers=headers
            )
            with urllib.request.urlopen(req_new_chat) as response:
                if response.status == 200:
                    chat_data = json.load(response)
                    chat_id = chat_data.get("id")
                    if not chat_id:
                        return jsonify({"error": "No se pudo obtener chat_id"}), 500

                    conversation = [{"role": "user", "content": first_prompt}]

                    def call_ollama_api(messages):
                        assistant_msg_id = str(uuid.uuid4())
                        session_id = str(uuid.uuid4())
                        stream_payload = json.dumps({
                            "stream": True,
                            "model": model,
                            "messages": messages,
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
                        with urllib.request.urlopen(stream_req) as stream_res:
                            for line in stream_res:
                                line = line.strip()
                                if line:
                                    chunk = json.loads(line)
                                    if "message" in chunk and "content" in chunk["message"]:
                                        assistant_content += chunk["message"]["content"]
                        return assistant_content

                    first_generated = call_ollama_api(conversation)
                    conversation.append({"role": "assistant", "content": first_generated})
                    results.append({
                        "prompt": first_prompt,
                        "expected_response": first_expected,
                        "response": first_generated,
                        "generated_response": first_generated
                    })

                    for item_p in processed_items[1:]:
                        p_prompt = item_p["prompt"]
                        p_expected = item_p["expected_response"]
                        msg_id = str(uuid.uuid4())
                        update_payload = json.dumps({
                            "chat": {
                                "models": [model],
                                "messages": [{
                                    "id": msg_id,
                                    "parentId": None,
                                    "childrenIds": [],
                                    "role": "user",
                                    "content": p_prompt,
                                    "timestamp": int(time.time() * 1000)
                                }]
                            }
                        }).encode("utf-8")

                        update_req = urllib.request.Request(
                            f"{server_url}/api/v1/chats/{chat_id}",
                            data=update_payload,
                            headers=headers,
                            method="POST"
                        )
                        with urllib.request.urlopen(update_req) as update_res:
                            if update_res.status != 200:
                                details_err = update_res.read().decode('utf-8')
                                results.append({
                                    "prompt": p_prompt,
                                    "expected_response": p_expected,
                                    "response": f"Error: {details_err}",
                                    "generated_response": f"Error: {details_err}"
                                })
                                continue

                        conversation.append({"role": "user", "content": p_prompt})
                        gen_resp = call_ollama_api(conversation)
                        conversation.append({"role": "assistant", "content": gen_resp})

                        results.append({
                            "prompt": p_prompt,
                            "expected_response": p_expected,
                            "response": gen_resp,
                            "generated_response": gen_resp
                        })

                    delete_payload = json.dumps({"force": True}).encode("utf-8")
                    delete_req = urllib.request.Request(
                        f"{server_url}/api/v1/chats/{chat_id}",
                        data=delete_payload,
                        headers=headers,
                        method="DELETE"
                    )
                    try:
                        with urllib.request.urlopen(delete_req):
                            pass
                    except Exception as e_del:
                        print(f"No se pudo borrar el chat {chat_id}: {e_del}")
                else:
                    details = response.read().decode("utf-8")
                    return jsonify({"error": f"Error al inicializar el chat: {details}"}), 500

        except urllib.error.HTTPError as e_http:
            details = e_http.read().decode("utf-8")
            return jsonify({"error": f"HTTPError: {details}"}), e_http.code
        except urllib.error.URLError as e_url:
            return jsonify({"error": f"URLError: {str(e_url)}"}), 500
        except Exception as e_general:
            return jsonify({"error": f'Excepción general: {str(e_general)}'}), 500

        session['evaluation_data'] = results

        return render_template('loadbank_results.html', results=results)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

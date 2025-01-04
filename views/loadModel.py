import sys
import json
import time
import uuid
from flask import Blueprint, jsonify, render_template, request, session, url_for
import urllib.request
import urllib.error

from views.data_storage import results_storage

loadModel_blueprint = Blueprint('loadModel', __name__)

MODELS_DATA = []


@loadModel_blueprint.route('/loadModelsJson', methods=['POST'])
def load_models_json():
    file = request.files.get('models-json')
    if not file:
        return jsonify({"error": "No se subió ningún archivo JSON de modelos."}), 400

    try:
        models_list = json.load(file)
    except Exception as e:
        return jsonify({"error": f"Error parseando el JSON de modelos: {str(e)}"}), 400

    if not isinstance(models_list, list):
        return jsonify({"error": "El archivo JSON de modelos debe ser una lista ([])"}), 400

    MODELS_DATA.clear()
    MODELS_DATA.extend(models_list)

    for m in MODELS_DATA:
        print(f"   - ID: {m.get('id')}")

    return jsonify({"success": True, "count": len(MODELS_DATA)})


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
                err_txt = resp.read().decode('utf-8')
                return None
    except urllib.error.HTTPError as e:
        err_txt = e.read().decode('utf-8')
        return None
    except urllib.error.URLError as e:
        return None


@loadModel_blueprint.route('/loadModel', methods=['GET'])
def load_model():
    return render_template('loadModel.html')


def build_files_for_knowledge(model_id):

    model_data = next((m for m in MODELS_DATA if m.get("id") == model_id), None)
    if not model_data:
        return []

    meta = model_data.get("info", {}).get("meta", {})
    knowledge_list = meta.get("knowledge", [])
    if not knowledge_list:
        return []

    files_array = []
    for kn_item in knowledge_list:
        file_dict = {
            "id": kn_item["id"],
            "name": kn_item.get("name", ""),
            "description": kn_item.get("description", ""),
            "type": kn_item.get("type", "collection")
        }
        files_array.append(file_dict)

    return files_array



@loadModel_blueprint.route('/runDataset', methods=['POST'])
def run_dataset():
    session.pop('job_id', None)

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

        dataset_filename = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename

        try:
            prompts_json = json.load(file)
        except Exception as e:
            return jsonify({"error": f"Error parsing dataset JSON: {str(e)}"}), 400

        processed_items = []
        for item in prompts_json:
            if ("prompt" not in item or
                "response" not in item or
                not isinstance(item["response"], dict) or
                "model_response" not in item["response"]):
                return jsonify({
                    "error": "El JSON no contiene la estructura requerida (prompt / response->model_response)."
                }), 400

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

        files_array = build_files_for_knowledge(model)

        first_prompt = processed_items[0]["prompt"]
        first_expected = processed_items[0]["expected_response"]
        user_msg_id = str(uuid.uuid4())

        initial_payload_dict = {
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
        }
        if files_array:
            initial_payload_dict["chat"]["files"] = files_array

        initial_payload = json.dumps(initial_payload_dict).encode("utf-8")

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

                        stream_payload_dict = {
                            "stream": True,
                            "model": model,
                            "messages": messages,
                            "options": {},
                            "session_id": session_id,
                            "chat_id": chat_id,
                            "id": assistant_msg_id
                        }
                        if files_array:
                            stream_payload_dict["files"] = files_array

                        stream_payload = json.dumps(stream_payload_dict).encode("utf-8")

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

                    for i, item_p in enumerate(processed_items[1:], start=2):
                        p_prompt = item_p["prompt"]
                        p_expected = item_p["expected_response"]
                        msg_id = str(uuid.uuid4())

                        update_payload_dict = {
                            "chat": {
                                "models": [model],
                                "params": {},
                                "messages": [{
                                    "id": msg_id,
                                    "parentId": None,
                                    "childrenIds": [],
                                    "role": "user",
                                    "content": p_prompt,
                                    "timestamp": int(time.time() * 1000)
                                }]
                            }
                        }
                        if files_array:
                            update_payload_dict["chat"]["files"] = files_array

                        update_payload = json.dumps(update_payload_dict).encode("utf-8")

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
                        print(f"[DEBUG] No se pudo borrar el chat {chat_id}: {e_del}")

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

        job_id = str(uuid.uuid4())
        results_storage[job_id] = {
            "results": results,
            "dataset_name": dataset_filename,
            "model_name": model
        }

        session['job_id'] = job_id
        redirect_url = url_for('loadModel.loadbank_results', page=1, per_page=10, job_id=job_id)
        return jsonify({"success": True, "redirect_url": redirect_url})

    except Exception as ex:
        return jsonify({"error": str(ex)}), 500
    


@loadModel_blueprint.route('/loadbank_results', methods=['GET'])
def loadbank_results():
    job_id = request.args.get('job_id') or session.get('job_id')
    if not job_id:
        return "No job_id provided (and none in session). Please run a dataset first.", 400

    data = results_storage.get(job_id)
    if not data:
        return f"No results found for job_id={job_id}.", 400

    results = data["results"]
    dataset_name = data["dataset_name"]
    model = data["model_name"]

    if not results:
        return "No data in this job. Please run a dataset first.", 400

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    valid_per_page = [5, 10, 25]
    if per_page not in valid_per_page:
        per_page = 10

    total = len(results)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_results = results[start_idx:end_idx]

    total_pages = (total // per_page) + (1 if total % per_page != 0 else 0)

    prev_args = {"page": page - 1, "per_page": per_page, "job_id": job_id}
    next_args = {"page": page + 1, "per_page": per_page, "job_id": job_id}

    return render_template(
        'loadbank_results.html',
        results=page_results,
        dataset_name=dataset_name,
        model=model,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        valid_per_page=valid_per_page,
        prev_args=prev_args,
        next_args=next_args
    )

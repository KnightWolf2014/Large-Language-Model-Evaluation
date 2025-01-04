import sqlite3
from flask import Blueprint, render_template, redirect, session, url_for, request
import logging
from datetime import datetime

from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

from views.data_storage import results_storage

evaluateResults_blueprint = Blueprint('evaluateResults', __name__)

# Función para calcular BLEU
def calculate_bleu(reference, candidate):
    if reference.strip() == candidate.strip():
        return 1.0
    reference_tokens = reference.split()
    candidate_tokens = candidate.split()
    smoothie = SmoothingFunction().method4
    score = sentence_bleu([reference_tokens], candidate_tokens, smoothing_function=smoothie)
    return score

# Función para calcular ROGUE-1, ROUGE-2 y ROUGE-L
def calculate_rouge(reference, candidate):
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
    scores = scorer.score(reference, candidate)
    return scores

# Función para calcular ROUGE-S
def calculate_rougeS(reference, candidate, max_skip=10):

    ref_tokens = reference.split()
    cand_tokens = candidate.split()
    
    ref_skip_bigrams = set()
    for i in range(len(ref_tokens)):
        for j in range(i+1, min(i+1+max_skip, len(ref_tokens))):
            ref_skip_bigrams.add((ref_tokens[i], ref_tokens[j]))

    cand_skip_bigrams = set()
    for i in range(len(cand_tokens)):
        for j in range(i+1, min(i+1+max_skip, len(cand_tokens))):
            cand_skip_bigrams.add((cand_tokens[i], cand_tokens[j]))

    overlap = ref_skip_bigrams.intersection(cand_skip_bigrams)
    overlap_count = len(overlap)
    ref_count = len(ref_skip_bigrams)
    cand_count = len(cand_skip_bigrams)

    if cand_count > 0:
        precision = overlap_count / cand_count
    else:
        precision = 0.0

    if ref_count > 0:
        recall = overlap_count / ref_count
    else:
        recall = 0.0

    if (precision + recall) > 0:
        fmeasure = 2 * precision * recall / (precision + recall)
    else:
        fmeasure = 0.0

    return {
        "precision": precision,
        "recall": recall,
        "fmeasure": fmeasure
    }

@evaluateResults_blueprint.route('/results')
def evaluate_results():
    # Recuperamos job_id del query param o de la sesión
    job_id = request.args.get('job_id') or session.get('job_id')
    if not job_id:
        return "No job_id found. Please run a dataset first.", 400

    # Obtenemos los datos del almacén global
    data = results_storage.get(job_id)
    if not data:
        return f"No data found for job_id={job_id}", 400

    evaluation_data = data["results"]  # Lo que antes estaba en session['evaluation_data']

    if not evaluation_data:
        return "No evaluation data found", 400

    total = len(evaluation_data)
    if total == 0:
        return "No evaluation data found", 400

    # Paginación
    per_page = request.args.get('per_page', 5, type=int)
    if per_page not in [5, 10, 25]:
        per_page = 5

    page = request.args.get('page', 1, type=int)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    displayed_data = evaluation_data[start_idx:end_idx]

    bleu_scores = []
    rouge1_scores = []
    rouge2_scores = []
    rougel_scores = []
    rouges_scores = []

    line_metrics = []

    # Calcular métricas para TODOS los items
    for item in evaluation_data:
        ref = item.get("expected_response", "")
        gen = item.get("generated_response", "")
        if not ref or not gen:
            line_metrics.append({
                "bleu": 0.0,
                "rouge1": 0.0,
                "rouge2": 0.0,
                "rougel": 0.0,
                "rougeS": 0.0
            })
            continue

        # BLEU
        bleu_score = round(calculate_bleu(ref, gen), 4)

        # ROUGE-1, 2, L
        rouge_scores = calculate_rouge(ref, gen)
        r1 = round(rouge_scores['rouge1'].fmeasure, 4)
        r2 = round(rouge_scores['rouge2'].fmeasure, 4)
        rl = round(rouge_scores['rougeL'].fmeasure, 4)

        # ROUGE-S
        rouge_s = calculate_rougeS(ref, gen, max_skip=4)
        rs = round(rouge_s["fmeasure"], 4)

        bleu_scores.append(bleu_score)
        rouge1_scores.append(r1)
        rouge2_scores.append(r2)
        rougel_scores.append(rl)
        rouges_scores.append(rs)

        line_metrics.append({
            "bleu": bleu_score,
            "rouge1": r1,
            "rouge2": r2,
            "rougel": rl,
            "rougeS": rs
        })

    # Promedios
    avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0.0
    avg_rouge1 = sum(rouge1_scores) / len(rouge1_scores) if rouge1_scores else 0.0
    avg_rouge2 = sum(rouge2_scores) / len(rouge2_scores) if rouge2_scores else 0.0
    avg_rougel = sum(rougel_scores) / len(rougel_scores) if rougel_scores else 0.0
    avg_rougeS = sum(rouges_scores) / len(rouges_scores) if rouges_scores else 0.0

    total_pages = (total // per_page) + (1 if total % per_page != 0 else 0)

    displayed_with_metrics = []
    for i, item in enumerate(displayed_data, start=start_idx):
        displayed_with_metrics.append({
            "prompt": item["prompt"],
            "expected_response": item.get("expected_response", ""),
            "generated_response": item.get("generated_response", ""),
            "bleu": line_metrics[i]["bleu"],
            "rouge1": line_metrics[i]["rouge1"],
            "rouge2": line_metrics[i]["rouge2"],
            "rougel": line_metrics[i]["rougel"],
            "rougeS": line_metrics[i]["rougeS"]
        })

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    return render_template(
        'evaluation_results.html',
        total=total,
        avg_bleu=f"{avg_bleu:.4f}",
        avg_rouge1=f"{avg_rouge1:.4f}",
        avg_rouge2=f"{avg_rouge2:.4f}",
        avg_rougel=f"{avg_rougel:.4f}",
        avg_rougeS=f"{avg_rougeS:.4f}",
        results=displayed_with_metrics,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page
    )
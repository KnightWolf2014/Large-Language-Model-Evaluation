import sqlite3
from flask import Blueprint, render_template, redirect, session, url_for, request
import logging
from datetime import datetime

from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

evaluateResults_blueprint = Blueprint('evaluateResults', __name__)

def calculate_bleu(reference, candidate):
    if reference.strip() == candidate.strip():
        return 1.0
    reference_tokens = reference.split()
    candidate_tokens = candidate.split()
    smoothie = SmoothingFunction().method4
    score = sentence_bleu([reference_tokens], candidate_tokens, smoothing_function=smoothie)
    return score

def calculate_rouge(reference, candidate):
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
    scores = scorer.score(reference, candidate)
    return scores

@evaluateResults_blueprint.route('/results')
def evaluate_results():
    evaluation_data = session.get('evaluation_data', [])
    if not evaluation_data:
        return "No evaluation data found", 400

    total = len(evaluation_data)
    if total == 0:
        return "No evaluation data found", 400

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

    line_metrics = []

    for item in evaluation_data:
        ref = item.get("expected_response", "")
        gen = item.get("generated_response", "")
        if not ref or not gen:
            line_metrics.append({
                "bleu": 0.0,
                "rouge1": 0.0,
                "rouge2": 0.0,
                "rougel": 0.0
            })
            continue
        
        bleu_score = round(calculate_bleu(ref, gen), 4)
        rouge_scores = calculate_rouge(ref, gen)
        r1 = round(rouge_scores['rouge1'].fmeasure, 4)
        r2 = round(rouge_scores['rouge2'].fmeasure, 4)
        rl = round(rouge_scores['rougeL'].fmeasure, 4)

        bleu_scores.append(bleu_score)
        rouge1_scores.append(r1)
        rouge2_scores.append(r2)
        rougel_scores.append(rl)

        line_metrics.append({
            "bleu": bleu_score,
            "rouge1": r1,
            "rouge2": r2,
            "rougel": rl
        })

    avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0.0
    avg_rouge1 = sum(rouge1_scores) / len(rouge1_scores) if rouge1_scores else 0.0
    avg_rouge2 = sum(rouge2_scores) / len(rouge2_scores) if rouge2_scores else 0.0
    avg_rougel = sum(rougel_scores) / len(rougel_scores) if rougel_scores else 0.0

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
            "rougel": line_metrics[i]["rougel"]
        })

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    return render_template('evaluation_results.html',
                            total=total,
                            avg_bleu=f"{avg_bleu:.4f}",
                            avg_rouge1=f"{avg_rouge1:.4f}",
                            avg_rouge2=f"{avg_rouge2:.4f}",
                            avg_rougel=f"{avg_rougel:.4f}",
                            results=displayed_with_metrics,
                            page=page,
                            per_page=per_page,
                            total_pages=total_pages,
                            prev_page=prev_page,
                            next_page=next_page)

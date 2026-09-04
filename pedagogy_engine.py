"""Deterministic pedagogy checks for Vietnamese mathematics exams.

The engine is intentionally conservative: deterministic structural problems are
FAIL; signals that require professional judgement are MANUAL_REVIEW.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any


VALID_TYPES = {"mcq", "multiple_choice", "true_false", "tf", "short_answer", "short"}
VALID_LEVELS = {"nhận biết", "thông hiểu", "vận dụng", "vận dụng cao"}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _issue(code: str, severity: str, message: str, evidence: Any = "", suggestion: str = "") -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "evidence": evidence,
        "suggestion": suggestion,
    }


def _question_type(question: dict) -> str:
    value = _norm(question.get("type", "mcq"))
    aliases = {
        "trắc nghiệm": "mcq", "multiple_choice": "mcq",
        "đúng/sai": "true_false", "đúng_sai": "true_false", "tf": "true_false",
        "trả lời ngắn": "short_answer", "short": "short_answer",
    }
    return aliases.get(value, value)


def _question_audit(question: dict) -> dict:
    issues: list[dict] = []
    text = _norm(question.get("question"))
    q_type = _question_type(question)
    level = _norm(question.get("level"))
    topic = _norm(question.get("topic"))

    if not text:
        issues.append(_issue("PED_EMPTY", "FAIL", "Thiếu nội dung câu hỏi."))
    elif len(text) < 12:
        issues.append(_issue("PED_TOO_SHORT", "MANUAL_REVIEW", "Câu hỏi quá ngắn, cần kiểm tra tính rõ nghĩa.", len(text)))
    if len(text) > 1200:
        issues.append(_issue("PED_TOO_LONG", "MANUAL_REVIEW", "Câu hỏi quá dài, có thể gây quá tải đọc hiểu.", len(text)))
    if q_type not in {"mcq", "true_false", "short_answer"}:
        issues.append(_issue("PED_TYPE", "FAIL", "Loại câu hỏi không được hỗ trợ.", q_type))
    if not level:
        issues.append(_issue("PED_LEVEL_MISSING", "MANUAL_REVIEW", "Chưa gắn mức độ nhận thức."))
    elif level not in VALID_LEVELS:
        issues.append(_issue("PED_LEVEL_UNKNOWN", "MANUAL_REVIEW", "Mức độ nhận thức chưa chuẩn hóa.", level))
    if not topic:
        issues.append(_issue("PED_TOPIC_MISSING", "MANUAL_REVIEW", "Chưa gắn chủ đề kiến thức."))
    if not _norm(question.get("solution")):
        issues.append(_issue("PED_SOLUTION_MISSING", "MANUAL_REVIEW", "Chưa có lời giải hoặc hướng dẫn chấm."))

    ambiguous = ["có thể", "thường", "xấp xỉ"]
    hits = [term for term in ambiguous if term in text]
    if hits:
        issues.append(_issue("PED_AMBIGUOUS", "MANUAL_REVIEW", "Có từ ngữ cần kiểm tra ngữ cảnh để tránh mơ hồ.", hits))

    status = "FAIL" if any(x["severity"] == "FAIL" for x in issues) else (
        "MANUAL_REVIEW" if any(x["severity"] == "MANUAL_REVIEW" for x in issues) else "PASS"
    )
    return {"status": status, "type": q_type, "level": question.get("level", ""), "topic": question.get("topic", ""), "issues": issues}


def audit_pedagogy(exam: Any) -> dict:
    if not isinstance(exam, dict):
        return {
            "status": "FAIL",
            "summary": {"total": 0, "pass": 0, "fail": 0, "manual_review": 0, "score": 0.0},
            "exam_issues": [_issue("PED_EXAM_FORMAT", "FAIL", "Dữ liệu đề phải là một JSON object.")],
            "questions": [],
        }

    questions = exam.get("questions", [])
    exam_issues: list[dict] = []
    if not isinstance(questions, list) or not questions:
        exam_issues.append(_issue("PED_NO_QUESTIONS", "FAIL", "Đề chưa có danh sách câu hỏi."))
        questions = []

    rows = []
    for number, question in enumerate(questions, 1):
        if not isinstance(question, dict):
            result = {"status": "FAIL", "type": "", "level": "", "topic": "", "issues": [_issue("PED_QUESTION_FORMAT", "FAIL", "Câu hỏi phải là JSON object.")]}
        else:
            result = _question_audit(question)
        rows.append({"number": number, **result})

    levels = Counter(_norm(q.get("level")) for q in questions if isinstance(q, dict))
    if len(questions) >= 4 and len([x for x in levels if x]) < 2:
        exam_issues.append(_issue("PED_LEVEL_BALANCE", "MANUAL_REVIEW", "Đề có ít hơn hai mức độ nhận thức.", dict(levels)))

    counts = Counter(row["status"] for row in rows)
    fail = counts["FAIL"]
    review = counts["MANUAL_REVIEW"]
    passed = counts["PASS"]
    status = "FAIL" if fail or any(x["severity"] == "FAIL" for x in exam_issues) else (
        "MANUAL_REVIEW" if review or exam_issues else "PASS"
    )
    total = len(rows)
    penalty = 5 * sum(x["severity"] == "FAIL" for x in exam_issues) + 2 * sum(x["severity"] == "MANUAL_REVIEW" for x in exam_issues)
    score = round(max(0.0, 100.0 * (passed + 0.5 * review) / max(1, total) - penalty), 1)
    return {
        "status": status,
        "summary": {"total": total, "pass": passed, "fail": fail, "manual_review": review, "score": score},
        "exam_issues": exam_issues,
        "questions": rows,
    }

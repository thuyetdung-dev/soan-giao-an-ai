"""Prompts, JSON parsing and certificate helpers for Exam Factory V5.0."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


def parse_ai_json(raw: str) -> dict:
    if not raw or not str(raw).strip():
        raise ValueError("AI không trả về dữ liệu.")
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", str(raw).strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Không tìm thấy JSON hợp lệ trong phản hồi AI.")
        data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("Dữ liệu AI phải là một JSON object.")
    return data


def exam_generation_prompt(blueprint: dict, source_text: str = "") -> str:
    source_rule = (
        "Chỉ sử dụng kiến thức trong NGUỒN; không tự tạo dữ kiện trái nguồn."
        if source_text.strip() else
        "Dùng kiến thức Toán phổ thông chính xác; mọi đáp án phải tự kiểm tra độc lập."
    )
    schema = {
        "title": "Tên đề", "subject": "Toán", "grade": "Toán 12", "blueprint": blueprint,
        "questions": [{
            "id": "Q1", "type": "mcq", "topic": "", "level": "nhận biết",
            "question": "", "options": ["", "", "", ""], "answer_index": 0,
            "expected_answer": "", "solution": "", "check": {"type": "mcq_index", "correct_index": 0},
        }],
    }
    return f"""Bạn là hội đồng ra đề Toán theo Chương trình GDPT 2018.
Tạo đúng ma trận sau: {json.dumps(blueprint, ensure_ascii=False)}
{source_rule}
Yêu cầu bắt buộc:
- Tổng số câu, loại câu và mức độ phải khớp tuyệt đối ma trận.
- MCQ có đúng 4 phương án và duy nhất một đáp án đúng.
- Mỗi câu có lời giải, đáp án và trường check có thể kiểm chứng.
- Không gắn nhãn mức độ cao chỉ vì câu dài.
- Trả về duy nhất JSON hợp lệ, không Markdown.
Schema tham khảo: {json.dumps(schema, ensure_ascii=False)}
NGUỒN:
{source_text[:40000]}"""


def reviewer_prompt(role: str, exam: dict, math_report: dict, pedagogy_report: dict) -> str:
    role_instruction = {
        "math": "Kiểm tra tính đúng đắn Toán học, đáp án và lời giải.",
        "pedagogy": "Kiểm tra ngôn ngữ, mức độ, tính phù hợp học sinh và ma trận.",
        "adversarial": "Tìm phản ví dụ, dữ kiện thiếu, nhiều đáp án đúng và bẫy không chủ ý.",
    }.get(role, "Phản biện độc lập đề kiểm tra.")
    return f"""Bạn là phản biện độc lập. {role_instruction}
Không được đổi kết quả FAIL xác định của engine thành PASS.
Trả về duy nhất JSON dạng:
{{"role":"{role}","status":"PASS|REVIEW|FAIL","score":0,"findings":[{{"severity":"REVIEW","finding":"...","question_id":"Q1"}}]}}
ĐỀ: {json.dumps(exam, ensure_ascii=False)}
MATH REPORT: {json.dumps(math_report, ensure_ascii=False)}
PEDAGOGY REPORT: {json.dumps(pedagogy_report, ensure_ascii=False)}"""


def certificate(report: dict) -> dict:
    status = str(report.get("status", "MANUAL_REVIEW")).upper()
    certificate_status = {"PASS": "CERTIFIED", "FAIL": "REJECTED"}.get(status, "CONDITIONAL")
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, default=str)
    return {
        "version": "5.0.0",
        "certificate_status": certificate_status,
        "scope": "Kiểm tra tự động trong phạm vi các engine; giáo viên vẫn chịu trách nhiệm duyệt cuối.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "report_fingerprint": hashlib.sha256(payload.encode("utf-8")).hexdigest().upper(),
    }

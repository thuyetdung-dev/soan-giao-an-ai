"""Lesson Studio V6: schema normalization and conservative lesson QA."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any
from equation_engine import formula_diagnostics

ACTIVITIES = ["KHỞI ĐỘNG", "HÌNH THÀNH KIẾN THỨC", "LUYỆN TẬP", "VẬN DỤNG", "CỦNG CỐ"]
LAYOUTS = {"section", "concept", "process", "example", "practice", "compare", "visual", "quiz", "summary", "content"}


def _text(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize_lesson(data: Any, max_slides: int = 60) -> dict:
    if not isinstance(data, dict):
        raise ValueError("AI không trả về đúng cấu trúc bài giảng.")
    raw_slides = data.get("slides")
    if not isinstance(raw_slides, list) or not raw_slides:
        raise ValueError("Không tìm thấy danh sách slide.")
    slides = []
    for raw in raw_slides[:max_slides]:
        if not isinstance(raw, dict):
            continue
        bullets = raw.get("bullets", [])
        if not isinstance(bullets, list):
            bullets = [bullets]
        formulas = raw.get("formulas", [])
        if not isinstance(formulas, list):
            formulas = [formulas]
        activity = _text(raw.get("activity") or "HÌNH THÀNH KIẾN THỨC", 60).upper()
        layout = _text(raw.get("layout") or "content", 30).lower()
        slides.append({
            "title": _text(raw.get("title") or "Nội dung bài học", 160),
            "subtitle": _text(raw.get("subtitle"), 260),
            "activity": activity if activity in ACTIVITIES else "HÌNH THÀNH KIẾN THỨC",
            "layout": layout if layout in LAYOUTS else "content",
            "bullets": [_text(x, 550) for x in bullets[:8] if _text(x)],
            "formulas": [_text(x, 500) for x in formulas[:4] if _text(x)],
            "question": _text(raw.get("question"), 800),
            "product": _text(raw.get("product"), 500),
            "answer": _text(raw.get("answer"), 1600),
            "teacher_note": _text(raw.get("teacher_note"), 1600),
            "source_ref": _text(raw.get("source_ref"), 500),
            "graph": raw.get("graph") if isinstance(raw.get("graph"), dict) else None,
            "variation_table": raw.get("variation_table") if isinstance(raw.get("variation_table"), dict) else None,
        })
    if not slides:
        raise ValueError("Các slide AI tạo ra không hợp lệ.")
    objectives = data.get("objectives", [])
    if not isinstance(objectives, list): objectives = [objectives]
    return {"title": _text(data.get("title") or "Bài giảng Toán", 200), "objectives": [_text(x, 400) for x in objectives[:8] if _text(x)], "slides": slides}


def audit_lesson(lesson: dict, requested_slides: int, source_text: str = "") -> dict:
    slides = lesson.get("slides", [])
    issues = []
    activities = Counter(s.get("activity") for s in slides)
    layouts = Counter(s.get("layout") for s in slides)
    if abs(len(slides) - requested_slides) > max(3, round(requested_slides * .15)):
        issues.append({"severity":"REVIEW","code":"SLIDE_COUNT","message":f"Tạo {len(slides)} slide, lệch đáng kể so với {requested_slides} slide yêu cầu."})
    for activity in ACTIVITIES:
        if not activities[activity]:
            issues.append({"severity":"FAIL","code":"MISSING_ACTIVITY","message":f"Thiếu hoạt động {activity}."})
    if len(layouts) < 4 and len(slides) >= 12:
        issues.append({"severity":"REVIEW","code":"LAYOUT_VARIETY","message":"Bài giảng dùng dưới 4 kiểu bố cục, dễ gây đơn điệu."})
    titles = Counter(_text(s.get("title")).lower() for s in slides)
    repeats = [t for t,n in titles.items() if t and n >= 3]
    if repeats:
        issues.append({"severity":"REVIEW","code":"REPEATED_TITLES","message":"Một số tiêu đề lặp từ 3 lần trở lên.","evidence":repeats[:5]})
    rows=[]
    for i,s in enumerate(slides,1):
        row=[]; chars=sum(len(x) for x in s.get("bullets",[]))+len(s.get("question","")+s.get("answer",""))
        if chars>650 or len(s.get("bullets",[]))>6: row.append("Mật độ chữ cao")
        if not s.get("bullets") and not s.get("question") and not s.get("formulas") and not s.get("graph") and not s.get("variation_table") and s.get("layout")!="section": row.append("Thiếu nội dung chính")
        if s.get("layout") in {"practice","quiz"} and not s.get("question"): row.append("Thiếu câu hỏi/nhiệm vụ")
        if s.get("layout") in {"practice","quiz"} and not s.get("product"): row.append("Chưa nêu sản phẩm học tập")
        for formula in s.get("formulas",[]): row.extend(formula_diagnostics(formula))
        if source_text.strip() and not s.get("source_ref"): row.append("Chưa ghi tham chiếu nguồn trong Notes")
        rows.append({"slide":i,"title":s.get("title"),"status":"REVIEW" if row else "PASS","issues":row})
    if source_text.strip():
        source_words=set(re.findall(r"[a-zà-ỹ]{4,}",source_text.lower()))
        lesson_words=set(re.findall(r"[a-zà-ỹ]{4,}"," ".join([lesson.get("title","")]+[s.get("title","")+" "+" ".join(s.get("bullets",[])) for s in slides]).lower()))
        overlap=len(source_words & lesson_words)/max(1,len(lesson_words))
        if overlap<.18: issues.append({"severity":"REVIEW","code":"SOURCE_ALIGNMENT","message":"Từ vựng bài giảng ít giao với tài liệu nguồn; cần giáo viên kiểm tra bám nguồn.","evidence":round(overlap,2)})
    review_rows=sum(r["status"]=="REVIEW" for r in rows)
    status="FAIL" if any(i["severity"]=="FAIL" for i in issues) else "REVIEW" if issues or review_rows else "PASS"
    score=max(0,100-12*sum(i["severity"]=="FAIL" for i in issues)-5*sum(i["severity"]=="REVIEW" for i in issues)-2*review_rows)
    return {"version":"6.0.0","status":status,"score":score,"summary":{"slides":len(slides),"activities":dict(activities),"layouts":dict(layouts),"slides_to_review":review_rows},"issues":issues,"slides":rows}

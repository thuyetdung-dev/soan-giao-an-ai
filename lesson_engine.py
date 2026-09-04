"""Lesson Studio V6: schema normalization and conservative lesson QA."""
from __future__ import annotations

import re
import math
from collections import Counter
from typing import Any
from equation_engine import formula_diagnostics
try:
    import sympy as sp
except Exception:
    sp = None

ACTIVITIES = ["KHỞI ĐỘNG", "HÌNH THÀNH KIẾN THỨC", "LUYỆN TẬP", "VẬN DỤNG", "CỦNG CỐ"]
LAYOUTS = {"section", "concept", "process", "example", "practice", "compare", "visual", "quiz", "summary", "content"}


def _text(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


INLINE_REPLACEMENTS={
    r"\infty":"∞",r"\leq":"≤",r"\le":"≤",r"\geq":"≥",r"\ge":"≥",r"\neq":"≠",r"\ne":"≠",
    r"\Leftrightarrow":"⇔",r"\Rightarrow":"⇒",r"\rightarrow":"→",r"\backslash":"∖",r"\in":"∈",r"\pm":"±",r"\cdot":"·",r"\times":"×"
}


def _clean_inline_math(text: str) -> str:
    out=str(text)
    for _ in range(3):
        out=re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}",r"(\1)/(\2)",out)
        out=re.sub(r"\\sqrt\{([^{}]+)\}",r"√(\1)",out)
    for old,new in INLINE_REPLACEMENTS.items(): out=out.replace(old,new)
    out=out.replace(r"\{","{").replace(r"\}","}")
    return out


def _split_math_bullets(bullets: list[str], formulas: list[str]) -> tuple[list[str],list[str]]:
    clean=[]; maths=list(formulas)
    for raw in bullets:
        item=str(raw)
        if re.search(r"\\(?:frac|sqrt|begin\{|sum|int)",item):
            if ":" in item:
                prefix,formula=item.split(":",1); clean.append(_clean_inline_math(prefix.strip()+":")); maths.append(formula.strip().rstrip("."))
            else: maths.append(item.strip().rstrip("."))
        else: clean.append(_clean_inline_math(item))
    return clean,maths


def verify_variation_table(data: Any) -> tuple[bool,str]:
    if not isinstance(data,dict): return False,"Bảng biến thiên không đúng cấu trúc."
    points=data.get("points",[]); signs=data.get("interval_signs",[]); values=data.get("values",[]); expression=str(data.get("expression","")).strip()
    if len(points)<2 or len(signs)!=len(points)-1 or len(values)!=len(points): return False,"Số điểm, khoảng dấu và giá trị không khớp."
    if not expression: return False,"Thiếu expression để kiểm chứng độc lập bảng biến thiên."
    if sp is None: return False,"Máy chủ chưa có SymPy để kiểm chứng bảng biến thiên."
    try:
        x=sp.Symbol("x", real=True); expr=sp.sympify(expression.replace("^","**"),locals={"x":x,"sin":sp.sin,"cos":sp.cos,"tan":sp.tan,"sqrt":sp.sqrt,"log":sp.log,"exp":sp.exp})
        deriv=sp.diff(expr,x); numeric=[]
        for p in points:
            s=str(p).strip().replace("−","-")
            if "∞" in s or "infty" in s: numeric.append(None)
            else:
                try: numeric.append(float(sp.N(sp.sympify(s))))
                except Exception: numeric.append(None)
        for i,want in enumerate(signs):
            left,right=numeric[i],numeric[i+1]
            sample=(left+right)/2 if left is not None and right is not None else (right-1 if right is not None else left+1 if left is not None else 0)
            got=float(sp.N(deriv.subs(x,sample)))
            expected=str(want).strip().replace("−","-")
            if expected=="+" and got<=1e-8: return False,f"Dấu đạo hàm sai trên khoảng thứ {i+1}."
            if expected=="-" and got>=-1e-8: return False,f"Dấu đạo hàm sai trên khoảng thứ {i+1}."
        for i,(point,want) in enumerate(zip(numeric,values),1):
            if point is None or want in (None,""): continue
            actual=sp.N(expr.subs(x,point))
            if actual in (sp.zoo,sp.oo,-sp.oo) or getattr(actual,"is_finite",None) is False: continue
            wanted=str(want).strip().replace("−","-").replace("∞","oo")
            try:
                expected_value=float(sp.N(sp.sympify(wanted)))
                if not math.isclose(float(actual),expected_value,rel_tol=1e-7,abs_tol=1e-7):
                    return False,f"Giá trị hàm số sai tại mốc thứ {i}."
            except (TypeError,ValueError,sp.SympifyError):
                return False,f"Không đọc được giá trị tại mốc thứ {i}."
        return True,"Đã kiểm chứng dấu đạo hàm và giá trị hàm số từ expression."
    except Exception as exc: return False,f"Không kiểm chứng được bảng biến thiên: {exc}"


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
        bullets,formulas=_split_math_bullets([_text(x,550) for x in bullets[:8] if _text(x)],[_text(x,500) for x in formulas[:4] if _text(x)])
        activity = _text(raw.get("activity") or "HÌNH THÀNH KIẾN THỨC", 60).upper()
        layout = _text(raw.get("layout") or "content", 30).lower()
        slides.append({
            "title": _clean_inline_math(_text(raw.get("title") or "Nội dung bài học", 160)),
            "subtitle": _clean_inline_math(_text(raw.get("subtitle"), 260)),
            "activity": activity if activity in ACTIVITIES else "HÌNH THÀNH KIẾN THỨC",
            "layout": layout if layout in LAYOUTS else "content",
            "bullets": bullets,
            "formulas": formulas[:6],
            "question": _clean_inline_math(_text(raw.get("question"), 800)),
            "product": _clean_inline_math(_text(raw.get("product"), 500)),
            "answer": _clean_inline_math(_text(raw.get("answer"), 1600)),
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
        prose=" ".join([s.get("title",""),s.get("subtitle",""),*s.get("bullets",[]),s.get("question",""),s.get("product",""),s.get("answer","")])
        if re.search(r"\\[A-Za-z]+",prose):
            row.append("Còn lệnh LaTeX thô trong vùng văn bản")
            issues.append({"severity":"FAIL","code":"RAW_LATEX_IN_TEXT","message":f"Slide {i}: còn lệnh LaTeX trong textbox."})
        if s.get("variation_table"):
            ok,detail=verify_variation_table(s["variation_table"])
            if not ok:
                row.append("Bảng biến thiên chưa đạt: "+detail)
                issues.append({"severity":"FAIL","code":"UNVERIFIED_VARIATION_TABLE","message":f"Slide {i}: {detail}"})
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
    return {"version":"7.1.0","status":status,"score":score,"summary":{"slides":len(slides),"activities":dict(activities),"layouts":dict(layouts),"slides_to_review":review_rows},"issues":issues,"slides":rows}

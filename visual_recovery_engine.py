"""Deterministic visual recovery for LessonStudio V8.4."""
from __future__ import annotations

import base64
import copy
import io
import math
import re
from typing import Any

import sympy as sp
from PIL import Image

from safe_math_parser import parse_math_expression
from visual_engine import audit_visual_contract, infer_visual_requirement, visual_assets


def _python_expression(value: str) -> str:
    text=str(value or "").strip().strip("$")
    text=text.replace("−","-").replace("×","*").replace("÷","/").replace("^","**")
    text=re.sub(r"\\left|\\right", "", text)
    for _ in range(3):
        text=re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}",r"(\1)/(\2)",text)
        text=re.sub(r"\\sqrt\{([^{}]+)\}",r"sqrt(\1)",text)
    text=text.replace(r"\ln","log").replace(r"\log","log").replace(r"\sin","sin").replace(r"\cos","cos")
    text=text.replace("{","(").replace("}",")")
    return text.strip()


def infer_expression(slide: dict) -> str:
    """Extract an explicit f(x)=... or y=... only; never invent a function."""
    candidates=[*(slide.get("formulas") or []),*(slide.get("bullets") or []),slide.get("question","")]
    for raw in candidates:
        text=str(raw or "")
        matches=re.findall(r"(?:y|f\s*\(\s*x\s*\))\s*=\s*([^.;\n]+)",text,re.IGNORECASE)
        for match in matches:
            expression=_python_expression(match)
            try:
                x=sp.Symbol("x",real=True); expr=parse_math_expression(expression,{"x":x})
                if not (expr.free_symbols-{x}): return expression
            except Exception:
                continue
    return ""


def _fmt(value: Any) -> str:
    if value == sp.oo: return "+∞"
    if value == -sp.oo: return "-∞"
    value=sp.simplify(value)
    return str(value).replace("**","^")


def build_variation_table(expression: str) -> tuple[dict|None,str]:
    """Build a compact verified table for functions with finite real breakpoints."""
    try:
        x=sp.Symbol("x",real=True); expr=parse_math_expression(expression,{"x":x}); deriv=sp.diff(expr,x)
        domain=sp.calculus.util.continuous_domain(expr,x,sp.S.Reals)
        roots=sp.solveset(sp.Eq(deriv,0),x,domain=domain)
        if roots == sp.S.EmptySet: roots=[]
        elif isinstance(roots,sp.FiniteSet): roots=list(roots)
        else: return None,"Không tìm được hữu hạn điểm tới hạn."
        denominator=sp.denom(sp.together(expr)); poles=sp.solveset(sp.Eq(denominator,0),x,domain=sp.S.Reals)
        if poles == sp.S.EmptySet: poles=[]
        elif isinstance(poles,sp.FiniteSet): poles=list(poles)
        else: return None,"Không tìm được hữu hạn điểm gián đoạn."
        breaks=sorted(set(roots)|set(poles),key=lambda z:float(sp.N(z)))
        if len(breaks)>8: return None,"Quá nhiều mốc cho một bảng biến thiên trên slide."
        bounds=[-sp.oo,*breaks,sp.oo]; signs=[]
        for left,right in zip(bounds,bounds[1:]):
            sample=(left+right)/2 if left != -sp.oo and right != sp.oo else right-1 if left == -sp.oo else left+1
            val=sp.N(deriv.subs(x,sample))
            if not val.is_real or not val.is_finite: return None,"Không xác định được dấu đạo hàm trên mọi khoảng."
            signs.append("+" if float(val)>0 else "-" if float(val)<0 else "0")
        values=[]
        for index,point in enumerate(bounds):
            if point == -sp.oo: value=sp.limit(expr,x,-sp.oo)
            elif point == sp.oo: value=sp.limit(expr,x,sp.oo)
            elif point in poles: return None,"Hàm có điểm gián đoạn; cần giáo viên duyệt giới hạn trái/phải."
            else: value=expr.subs(x,point)
            values.append(_fmt(value))
        table={"expression":expression,"points":[_fmt(x) for x in bounds],"interval_signs":signs,"values":values,
               "recovery_status":"AUTO_GENERATED","teacher_approved":False}
        return table,"Đã tự dựng từ biểu thức và cần giáo viên duyệt."
    except Exception as exc:
        return None,f"Không tự dựng được bảng: {exc}"


def recover_slide_visual(slide: dict) -> tuple[dict,dict]:
    out=copy.deepcopy(slide); contract=infer_visual_requirement(out); expression=infer_expression(out)
    result={"status":"NO_ACTION","message":"Slide không thiếu visual.","expression":expression}
    if not audit_visual_contract(out,1): return out,result
    types=contract.get("types",[])
    if "variation_table" in types and expression:
        table,detail=build_variation_table(expression)
        if table:
            out["variation_table"]=table
            return out,{"status":"AUTO_GENERATED","type":"variation_table","message":detail,"expression":expression}
    if "function_graph" in types and expression:
        out["graph"]={"expression":expression,"x_min":-5,"x_max":5,"caption":f"Đồ thị y = {expression}",
                      "recovery_status":"AUTO_GENERATED","teacher_approved":False}
        return out,{"status":"AUTO_GENERATED","type":"function_graph","message":"Đã dựng cấu hình đồ thị; cần giáo viên duyệt.","expression":expression}
    return out,{"status":"WAITING_FOR_TEACHER_ASSET","type":types[0] if types else "source_image",
                "message":"Không đủ dữ liệu Toán học để tự dựng an toàn; hãy tải hình hoặc bổ sung biểu thức.","expression":expression}


def recover_lesson_visuals(lesson: dict) -> tuple[dict,list[dict]]:
    out=copy.deepcopy(lesson); results=[]
    for index,slide in enumerate(out.get("slides",[]),1):
        fixed,result=recover_slide_visual(slide); out["slides"][index-1]=fixed
        if result["status"]!="NO_ACTION": results.append({"slide":index,"title":slide.get("title",""),**result})
    return out,results


def attach_teacher_asset(slide: dict, data: bytes, filename: str, mime_type: str) -> dict:
    if not data or len(data)>12*1024*1024: raise ValueError("Ảnh phải có dung lượng từ 1 byte đến 12 MB.")
    try:
        image=Image.open(io.BytesIO(data)); image.verify()
    except Exception as exc: raise ValueError("Tệp không phải ảnh hợp lệ.") from exc
    if image.format not in {"PNG","JPEG","WEBP"}: raise ValueError("Chỉ hỗ trợ PNG, JPG/JPEG hoặc WEBP.")
    out=copy.deepcopy(slide)
    out["image_asset"]={"name":filename,"mime_type":mime_type or Image.MIME.get(image.format,"image/png"),
                        "data_base64":base64.b64encode(data).decode("ascii"),"recovery_status":"UPLOADED_BY_TEACHER",
                        "teacher_approved":True}
    return out


def pending_visuals(lesson: dict) -> list[dict]:
    rows=[]
    for index,slide in enumerate(lesson.get("slides",[]),1):
        issues=audit_visual_contract(slide,index)
        if issues: rows.append({"slide":index,"title":slide.get("title",""),"issues":[x["message"] for x in issues],
                                "has_assets":sorted(visual_assets(slide))})
    return rows


def approve_recovered_visuals(lesson: dict, slide_number: int|None=None) -> dict:
    out=copy.deepcopy(lesson)
    for index,slide in enumerate(out.get("slides",[]),1):
        if slide_number is not None and index!=slide_number: continue
        for key in ("graph","variation_table"):
            asset=slide.get(key)
            if isinstance(asset,dict) and asset.get("recovery_status")=="AUTO_GENERATED":
                asset["teacher_approved"]=True
    return out

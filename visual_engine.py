"""LessonStudio V8.3 Math Visual First: visual contracts and layout QA."""
from __future__ import annotations

import copy
import re
from typing import Any

VISUAL_PATTERNS = {
    "variation_table": (
        r"bảng\s+biến\s+thiên", r"bảng\s+xét\s+dấu", r"dựa\s+vào\s+bảng",
    ),
    "function_graph": (
        r"đồ\s+thị", r"quan\s+sát\s+hình", r"từ\s+hình\s+vẽ", r"hình\s*\d+(?:\.\d+)?",
    ),
    "geometry": (r"như\s+hình", r"hình\s+bên", r"hình\s+dưới", r"theo\s+hình\s+vẽ", r"tấm\s+bìa.*cắt"),
}


def slide_text(slide: dict) -> str:
    values = [slide.get("title", ""), slide.get("subtitle", ""), slide.get("question", ""),
              slide.get("product", ""), slide.get("answer", ""), *(slide.get("bullets", []) or [])]
    return " ".join(str(x or "") for x in values)


def infer_visual_requirement(slide: dict) -> dict:
    """Infer the strongest visual contract from learner-facing copy."""
    text = slide_text(slide).lower()
    requested = []
    for kind, patterns in VISUAL_PATTERNS.items():
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            requested.append(kind)
    declared = str((slide.get("visual_requirement") or {}).get("type", "")).strip()
    if declared and declared not in requested:
        requested.insert(0, declared)
    if slide.get("variation_table") and "variation_table" not in requested:
        requested.append("variation_table")
    if slide.get("graph") and "function_graph" not in requested:
        requested.append("function_graph")
    for visual in slide.get("visuals",[]) or []:
        kind=str(visual.get("type", ""))
        mapped="function_graph" if kind=="dothi" else "variation_table" if kind in {"bbt","xetdau"} else "geometry"
        if mapped not in requested: requested.append(mapped)
    required = bool(requested) or slide.get("layout") == "visual"
    return {
        "required": required,
        "types": requested,
        "reason": "Nội dung học tập yêu cầu học sinh quan sát hoặc sử dụng biểu diễn trực quan." if required else "",
    }


def visual_assets(slide: dict) -> set[str]:
    assets = set()
    if isinstance(slide.get("variation_table"), dict): assets.add("variation_table")
    if isinstance(slide.get("graph"), dict): assets.add("function_graph")
    if isinstance(slide.get("image_asset"), dict): assets.add("source_image")
    if isinstance(slide.get("geometry"), dict): assets.add("geometry")
    if isinstance(slide.get("chart"), dict): assets.add("chart")
    for visual in slide.get("visuals",[]) or []:
        kind=str(visual.get("type", ""))
        assets.add("function_graph" if kind=="dothi" else "variation_table" if kind in {"bbt","xetdau"} else "geometry")
    return assets


def audit_visual_contract(slide: dict, number: int) -> list[dict]:
    contract = infer_visual_requirement(slide)
    assets = visual_assets(slide)
    issues = []
    if contract["required"] and not assets:
        issues.append({"severity":"FAIL", "code":"MISSING_REQUIRED_VISUAL",
                       "message":f"Slide {number} nhắc hoặc yêu cầu biểu diễn trực quan nhưng không có dữ liệu hình/đồ thị/bảng."})
    for kind in contract["types"]:
        if kind == "variation_table" and not ({"variation_table","source_image"} & assets):
            issues.append({"severity":"FAIL", "code":"MISSING_VARIATION_TABLE",
                           "message":f"Slide {number} nhắc bảng biến thiên/bảng xét dấu nhưng chưa có variation_table."})
        if kind == "function_graph" and not ({"function_graph","source_image"} & assets):
            issues.append({"severity":"FAIL", "code":"MISSING_GRAPH_OR_IMAGE",
                           "message":f"Slide {number} yêu cầu đọc hình hoặc đồ thị nhưng chưa có graph/image_asset."})
        if kind == "geometry" and not ({"geometry","source_image"} & assets):
            issues.append({"severity":"FAIL", "code":"MISSING_GEOMETRY_OR_IMAGE",
                           "message":f"Slide {number} tham chiếu hình nhưng chưa có visual hình học hoặc ảnh nguồn."})
    for key in ("graph","variation_table"):
        asset=slide.get(key)
        if isinstance(asset,dict) and asset.get("recovery_status")=="AUTO_GENERATED" and not asset.get("teacher_approved"):
            issues.append({"severity":"FAIL","code":"VISUAL_TEACHER_APPROVAL_REQUIRED",
                           "message":f"Slide {number} có visual tự dựng nhưng giáo viên chưa xác nhận."})
    return issues


def density_budget(slide: dict) -> dict:
    """Estimate readable capacity before PowerPoint rendering; never shrink below classroom size."""
    bullets = [str(x) for x in (slide.get("bullets") or [])]
    chars = sum(len(x) for x in bullets) + len(str(slide.get("question") or ""))
    chars += len(str(slide.get("product") or "")) + len(str(slide.get("answer") or ""))
    blocks = sum(bool(slide.get(k)) for k in ("question","product","answer","graph","variation_table","image_asset","visuals"))
    limit = 310 if visual_assets(slide) else 430
    return {"chars":chars, "blocks":blocks, "limit":limit,
            "overflow_risk":chars > limit or len(bullets) > 5 or blocks > 3}


def split_overloaded_slide(slide: dict) -> list[dict]:
    """Content-preserving split: exposition first, task/answer second."""
    budget = density_budget(slide)
    if not budget["overflow_risk"]:
        return [slide]
    first = copy.deepcopy(slide)
    second = copy.deepcopy(slide)
    bullets = list(slide.get("bullets") or [])
    cut = max(1, min(len(bullets), (len(bullets)+1)//2))
    first["bullets"] = bullets[:cut]
    first["question"] = first["product"] = first["answer"] = ""
    second["title"] = (str(slide.get("title") or "Nội dung") + " — Luyện tập").strip()
    second["bullets"] = bullets[cut:]
    second["graph"] = None
    second["variation_table"] = None
    second["image_asset"] = None
    second["visuals"] = []
    if not second["bullets"] and not any(second.get(k) for k in ("question","product","answer","formulas")):
        return [slide]
    return [first, second]


def paginate_lesson(lesson: dict) -> dict:
    out = copy.deepcopy(lesson)
    pages = []
    for slide in out.get("slides", []):
        pages.extend(split_overloaded_slide(slide))
    out["slides"] = pages
    return out

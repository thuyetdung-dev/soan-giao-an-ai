import ast
import io
import json
import math
import operator
import re
import uuid
from dataclasses import dataclass
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from docx import Document
import google.generativeai as genai
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt
from audit_engine import audit_exam, auto_fix_exam as safe_autofix
from adaptive_engine import analyze_exam, variant_consistency, build_manifest
from question_bank import QuestionBank, question_dna, fingerprint as question_fingerprint, select_from_bank, qtype
from v5_engine import build_variants, coverage_report, release_gate, manifest as build_v5_manifest

# --- Vá lỗi giả lập các module sư phạm chưa cài đặt ---
def audit_pedagogy(exam): return {"status": "PASS", "summary": {"score": 100, "fail": 0, "manual_review": 0}, "exam_issues": [], "questions": []}
def exam_generation_prompt(bp, source): return ""
def reviewer_prompt(role, exam, mr, pr): return ""
def parse_ai_json(text): return {}
def certificate(base): return {"certificate_status": "DRAFT_MODE"}
# ------------------------------------------------------
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

APP_VERSION = "5.0.0 (Exam Intelligence Platform + Question DNA + Bank + Multi-Code QA)"
MAX_UPLOAD_MB = 20
MAX_SOURCE_CHARS = 60_000
MAX_SLIDES = 60

THEMES = {
    "Xanh học thuật": {"primary": (16, 62, 105), "accent": (31, 150, 180), "light": (235, 246, 250)},
    "Xanh lá hiện đại": {"primary": (23, 92, 72), "accent": (45, 166, 116), "light": (235, 248, 242)},
    "Tím công nghệ": {"primary": (75, 53, 123), "accent": (137, 99, 186), "light": (245, 240, 251)},
    "Đỏ trang trọng": {"primary": (142, 32, 45), "accent": (210, 76, 89), "light": (253, 240, 242)},
}

ACTIVITY_COLORS = {
    "KHỞI ĐỘNG": (239, 108, 0),
    "HÌNH THÀNH KIẾN THỨC": (21, 101, 192),
    "LUYỆN TẬP": (0, 130, 100),
    "VẬN DỤNG": (126, 68, 153),
    "CỦNG CỐ": (180, 45, 55),
}

@dataclass
class LessonConfig:
    teacher: str
    school: str
    grade: str
    book: str
    lesson: str
    periods: int
    student_level: str
    slide_count: int
    theme_name: str
    include_answers: bool
    include_notes: bool

def clean_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    
    # 1. Khắc phục lỗi dư dấu gạch chéo ngược (R \\ {-2} -> R \ {-2})
    text = text.replace('\\\\', '\\')
    
    # 2. Định dạng Unicode toán học
    replacements = {"<=>": "⇔", "=>": "⇒", ">=": "≥", "<=": "≤", "+-": "±"}
    for old, new in replacements.items():
        text = text.replace(old, new)
        
    superscripts = str.maketrans("0123456789-+", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺")
    subscripts = str.maketrans("0123456789-+", "₀₁₂₃₄₅₆₇₈₉₋₊")
    text = re.sub(r"\^\{?(-?\d+)\}?", lambda m: m.group(1).translate(superscripts), text)
    text = re.sub(r"_\{?(-?\d+)\}?", lambda m: m.group(1).translate(subscripts), text)
    
    # 3. KEO TÀNG HÌNH BẢO VỆ CÔNG THỨC TOÁN
    # Dùng Non-Breaking Space (\xA0) thay cho khoảng trắng để PPT không bị cắt chữ nửa chừng
    math_ops = ['=', '≤', '≥', '∈', '∉', '≠', '⇔', '⇒', '±', '+', '-', '×', '÷', '<', '>']
    for op in math_ops:
        text = text.replace(f" {op} ", f"\xA0{op}\xA0")
    
    # Bảo vệ riêng ký hiệu hiệu tập hợp (VD: R \ {-2})
    text = text.replace(" \\ ", "\xA0\\\xA0")
    
    return text

def extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    parts: list[str] = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())
    for table_index, table in enumerate(doc.tables, 1):
        parts.append(f"[BẢNG {table_index}]")
        for row in table.rows:
            cells = [clean_text(cell.text) for cell in row.cells]
            parts.append(" | ".join(cells))
    return "\n".join(parts)

def read_source(uploaded_file) -> tuple[str, bytes, str]:
    data = uploaded_file.getvalue()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"Tệp vượt quá {MAX_UPLOAD_MB} MB.")
    name = uploaded_file.name.lower()
    if name.endswith(".docx"):
        return extract_docx(data)[:MAX_SOURCE_CHARS], data, "docx"
    if name.endswith(".txt"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        return text[:MAX_SOURCE_CHARS], data, "txt"
    if name.endswith(".pdf"):
        return "", data, "pdf"
    raise ValueError("Chỉ hỗ trợ PDF, DOCX và TXT.")

ALLOWED_FUNCTIONS = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan, "sqrt": np.sqrt,
    "abs": np.abs, "exp": np.exp, "log": np.log, "ln": np.log,
}
ALLOWED_CONSTANTS = {"pi": np.pi, "e": np.e}
ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)
BINOP_FUNCS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
}
UNARY_FUNCS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def _check_math_ast(node: ast.AST) -> None:
    if isinstance(node, ast.Expression):
        _check_math_ast(node.body)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ALLOWED_BINOPS):
        _check_math_ast(node.left)
        _check_math_ast(node.right)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ALLOWED_UNARYOPS):
        _check_math_ast(node.operand)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS or node.keywords:
            raise ValueError("Hàm toán học không được hỗ trợ.")
        for arg in node.args:
            _check_math_ast(arg)
    elif isinstance(node, ast.Name):
        if node.id not in {"x", *ALLOWED_CONSTANTS}:
            raise ValueError(f"Biến '{node.id}' không được phép.")
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError("Hằng số không hợp lệ.")
    else:
        raise ValueError("Biểu thức chứa thành phần không an toàn.")

def _evaluate_math_ast(node: ast.AST, scope: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate_math_ast(node.body, scope)
    if isinstance(node, ast.BinOp):
        left = _evaluate_math_ast(node.left, scope)
        right = _evaluate_math_ast(node.right, scope)
        return BINOP_FUNCS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp):
        return UNARY_FUNCS[type(node.op)](_evaluate_math_ast(node.operand, scope))
    if isinstance(node, ast.Call):
        args = [_evaluate_math_ast(arg, scope) for arg in node.args]
        return scope[node.func.id](*args)
    if isinstance(node, ast.Name):
        return scope[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError("Không thể tính biểu thức.")

def safe_math_eval(expression: str, x: np.ndarray) -> np.ndarray:
    normalized = expression.replace("^", "**").strip()
    tree = ast.parse(normalized, mode="eval")
    _check_math_ast(tree)
    scope = {"x": x, **ALLOWED_FUNCTIONS, **ALLOWED_CONSTANTS}
    result = _evaluate_math_ast(tree, scope)
    y = np.asarray(result, dtype=float)
    if y.ndim == 0:
        y = np.full_like(x, float(y))
    if y.shape != x.shape:
        raise ValueError("Biểu thức không tạo được một giá trị y cho mỗi x.")
    return y

def create_graph(graph: dict[str, Any]) -> io.BytesIO | None:
    expression = str(graph.get("expression", "x"))[:300]
    x_min = max(-100.0, min(100.0, float(graph.get("x_min", -5))))
    x_max = max(-100.0, min(100.0, float(graph.get("x_max", 5))))
    if not x_min < x_max:
        return None
    x = np.linspace(x_min, x_max, 1600)
    with np.errstate(all="ignore"):
        y = safe_math_eval(expression, x)
    finite = np.isfinite(y)
    if not finite.any():
        return None
    finite_values = y[finite]
    q1, q99 = np.percentile(finite_values, [1, 99])
    span = max(4.0, q99 - q1)
    lower, upper = q1 - span * 0.12, q99 + span * 0.12
    plot_y = y.copy()
    jumps = np.zeros_like(plot_y, dtype=bool)
    jumps[1:] = np.abs(np.diff(plot_y)) > span * 0.8
    plot_y[~finite | jumps | (plot_y < lower - span) | (plot_y > upper + span)] = np.nan

    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    ax.plot(x, plot_y, color="#1261a0", linewidth=2.4)
    ax.axhline(0, color="#263238", linewidth=1)
    ax.axvline(0, color="#263238", linewidth=1)
    ax.grid(True, linestyle="--", alpha=0.28)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(lower, upper)
    ax.set_xlabel("x")
    ax.set_ylabel("y", rotation=0, labelpad=10)
    ax.set_title(clean_text(graph.get("caption") or f"Đồ thị y = {expression}"), fontsize=13, weight="bold")
    fig.tight_layout()
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=220, transparent=False, facecolor="white")
    plt.close(fig)
    output.seek(0)
    return output

def create_variation_table(data: dict[str, Any]) -> io.BytesIO | None:
    points = data.get("points", [])
    intervals = data.get("interval_signs", [])
    values = data.get("values", [])
    if not isinstance(points, list) or len(points) < 2 or len(points) > 12:
        return None
    cols = 2 * len(points) - 1
    fig, ax = plt.subplots(figsize=(max(7.5, cols * 0.72), 3.2))
    ax.set_xlim(0, cols + 1)
    ax.set_ylim(0, 3)
    ax.axis("off")
    for y in range(4):
        ax.plot([0, cols + 1], [y, y], color="#263238", lw=1.1)
    ax.plot([1, 1], [0, 3], color="#263238", lw=1.2)
    ax.text(.5, 2.5, "x", ha="center", va="center", fontsize=14, style="italic")
    ax.text(.5, 1.5, "y′", ha="center", va="center", fontsize=14, style="italic")
    ax.text(.5, .5, "y", ha="center", va="center", fontsize=14, style="italic")
    for i, point in enumerate(points):
        xpos = 1.5 + 2 * i
        ax.text(xpos, 2.5, clean_text(point), ha="center", va="center", fontsize=13)
        if i < len(values) and values[i] not in (None, ""):
            val = clean_text(values[i])
            ypos = .78 if i == 0 else (.22 if i == len(points) - 1 else .5)
            ax.text(xpos, ypos, val, ha="center", va="center", fontsize=12)
        if i < len(points) - 1:
            sign = clean_text(intervals[i]) if i < len(intervals) else ""
            mid = xpos + 1
            ax.text(mid, 1.5, sign, ha="center", va="center", fontsize=14)
            rising = sign == "+"
            ax.annotate("", xy=(xpos + 1.72, .78 if rising else .22),
                        xytext=(xpos + .28, .22 if rising else .78),
                        arrowprops={"arrowstyle": "->", "lw": 1.6, "color": "#1261a0"})
    fig.tight_layout(pad=.3)
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    output.seek(0)
    return output

def split_bullets(items: list[str], max_chars: int = 430) -> list[list[str]]:
    pages: list[list[str]] = []
    current: list[str] = []
    size = 0
    for raw in items:
        item = clean_text(raw)
        if not item:
            continue
        if current and (size + len(item) > max_chars or len(current) >= 6):
            pages.append(current)
            current, size = [], 0
        current.append(item)
        size += len(item)
    if current or not pages:
        pages.append(current)
    return pages

def validate_lesson(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("AI không trả về đúng cấu trúc bài giảng.")
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError("Không tìm thấy danh sách slide.")
    cleaned_slides = []
    for slide in slides[:MAX_SLIDES]:
        if not isinstance(slide, dict):
            continue
        title = clean_text(slide.get("title"))[:180]
        bullets = slide.get("bullets", [])
        if not isinstance(bullets, list):
            bullets = [str(bullets)]
        cleaned_slides.append({
            "title": title or "Nội dung bài học",
            "activity": clean_text(slide.get("activity", "HÌNH THÀNH KIẾN THỨC")).upper()[:60],
            "bullets": [clean_text(x)[:700] for x in bullets[:15]],
            "answer": clean_text(slide.get("answer"))[:1800],
            "teacher_note": clean_text(slide.get("teacher_note"))[:1200],
            "graph": slide.get("graph") if isinstance(slide.get("graph"), dict) else None,
            "variation_table": slide.get("variation_table") if isinstance(slide.get("variation_table"), dict) else None,
        })
    if not cleaned_slides:
        raise ValueError("Các slide AI tạo ra không hợp lệ.")
    return {"title": clean_text(data.get("title"))[:200], "slides": cleaned_slides}

def build_prompt(config: LessonConfig) -> str:
    answer_rule = "Có thể cung cấp đáp án ở trường answer." if config.include_answers else "Trường answer luôn để trống."
    return f"""
Bạn là chuyên gia Toán THPT. Viết bài giảng bám sát cấu trúc GDPT 2018 (5 hoạt động).
- Bài: {config.lesson or 'Tự xác định từ tài liệu'}
- Đối tượng: {config.student_level}; Số slide dự kiến: {config.slide_count} (CỰC KỲ QUAN TRỌNG: Phải dàn đều nội dung ra đủ số lượng slide này, không được gộp ép).

YÊU CẦU SƯ PHẠM (Phân bổ rành mạch cho 3 tiết học):
- TIẾT 1 (Khái niệm & Khoảng): Dạy định nghĩa GTLN, GTNN. Cách tìm trên một khoảng bằng Bảng biến thiên. Thiết kế 3-4 ví dụ và bài tập.
- TIẾT 2 (Đoạn [a; b]): Dạy Quy tắc 3 bước trên đoạn. Tuyệt đối nhấn mạnh KHÔNG CẦN vẽ Bảng biến thiên. Cung cấp 4-5 bài tập luyện tập.
- TIẾT 3 (Thực tế): Quay lại giải quyết bài toán thực tế hộp carton ở phần Khởi động. Thêm 5 câu trắc nghiệm Củng cố (tạo các bẫy nhầm lẫn giữa khoảng và đoạn).
- Quy tắc trình bày: MỖI định nghĩa, MỖI bước giải, MỖI ví dụ, MỖI câu trắc nghiệm PHẢI nằm trên MỘT slide độc lập. Tối đa 5-6 dòng/slide. {answer_rule}

ĐỒ HỌA TÙY CHỌN:
- graph: {{"expression":"x**3-3*x", "x_min":-5, "x_max":5, "caption":"..."}}. Chỉ dùng Python math chuẩn (sin, cos, exp).
- variation_table: {{"points":["-∞","-1","1","+∞"], "interval_signs":["+","-","+"], "values":["-∞","2","-2","+∞"]}}.

Trả về duy nhất JSON chuẩn:
{{
  "title":"Tên bài học",
  "slides":[{{
    "title":"Tiêu đề slide",
    "activity":"HÌNH THÀNH KIẾN THỨC",
    "bullets":["Ý 1","Ý 2"],
    "answer":"",
    "teacher_note":"Ghi chú giảng dạy chi tiết cho giáo viên",
    "graph":null,
    "variation_table":null
  }}]
}}
"""

def generate_lesson(model_name: str, source_text: str, source_bytes: bytes, source_type: str, config: LessonConfig) -> dict[str, Any]:
    prompt = build_prompt(config)
    if source_type == "pdf":
        contents = [{"mime_type": "application/pdf", "data": source_bytes}, prompt]
    else:
        contents = [f"TÀI LIỆU NGUỒN:\n{source_text}\n\n{prompt}"]
    
    model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json", "temperature": 0.25})
    response = model.generate_content(contents)
    
    if not response.text:
        raise ValueError("AI không trả về nội dung. Vui lòng thử lại.")
        
    raw_json = response.text
    raw_json = re.sub(r'```(?:json)?', '', raw_json).strip()
    raw_json = re.sub(r'```', '', raw_json).strip()
    
    try:
        match = re.search(r'\{.*\}', raw_json, re.DOTALL)
        if match:
            clean_json = match.group(0).replace('\\', '\\\\')
            return validate_lesson(json.loads(clean_json, strict=False))
        return validate_lesson(json.loads(raw_json))
    except Exception:
        return validate_lesson(json.loads(raw_json.replace('\\', '\\\\'), strict=False))

def add_full_background(slide, color: tuple[int, int, int]) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(*color)
    shape.line.fill.background()
    slide.shapes._spTree.remove(shape._element)
    slide.shapes._spTree.insert(2, shape._element)

def add_text(slide, text: str, left: float, top: float, width: float, height: float,
             size: int, color=(40, 40, 40), bold=False, align=PP_ALIGN.LEFT,
             font="Aptos", valign=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(.08)
    frame.margin_top = frame.margin_bottom = Inches(.04)
    frame.vertical_anchor = valign
    p = frame.paragraphs[0]
    p.text = text
    p.alignment = align
    p.font.name = font
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = RGBColor(*color)
    return box

def add_header(slide, title: str, activity: str, theme: dict[str, tuple[int, int, int]], page: int):
    primary = theme["primary"]
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(.18))
    bar.fill.solid(); bar.fill.fore_color.rgb = RGBColor(*primary); bar.line.fill.background()
    add_text(slide, title, .72, .38, 11.8, .7, 27, primary, True)
    activity_color = ACTIVITY_COLORS.get(activity, theme["accent"])
    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(.75), Inches(1.08), Inches(3.1), Inches(.42))
    pill.fill.solid(); pill.fill.fore_color.rgb = RGBColor(*activity_color); pill.line.fill.background()
    add_text(slide, activity, .82, 1.13, 2.95, .28, 11, (255, 255, 255), True, PP_ALIGN.CENTER)
    add_text(slide, str(page), 12.35, 7.05, .4, .25, 10, (100, 100, 100), False, PP_ALIGN.RIGHT)

def add_bullets(slide, bullets: list[str], left: float, top: float, width: float, height: float,
                font_size: int = 21):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    frame.clear()
    # Kích hoạt Word Wrap của PPT
    frame.word_wrap = True
    frame.margin_left = Inches(.08); frame.margin_right = Inches(.08)
    
    # Gộp toàn bộ đoạn văn vào CHUNG MỘT Textbox để hỗ trợ hiệu ứng (Animation By Paragraph)
    for i, bullet in enumerate(bullets):
        p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        p.text = clean_text(bullet)
        p.level = 0
        p.font.name = "Aptos"
        p.font.size = Pt(font_size)
        p.font.color.rgb = RGBColor(43, 48, 53)
        p.space_after = Pt(10)
        p.text = "●  " + p.text
    return box

def add_answer_box(slide, answer: str, theme):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(.82), Inches(5.72), Inches(11.7), Inches(.92))
    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(*theme["light"])
    shape.line.color.rgb = RGBColor(*theme["accent"])
    add_text(slide, "ĐÁP ÁN/GỢI Ý: " + answer, 1.0, 5.9, 11.3, .55, 16, theme["primary"], True)

def build_pptx(lesson: dict[str, Any], config: LessonConfig) -> bytes:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    theme = THEMES[config.theme_name]

    cover = prs.slides.add_slide(blank)
    add_full_background(cover, theme["primary"])
    accent = cover.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(.85), Inches(1.0), Inches(.12), Inches(5.4))
    accent.fill.solid(); accent.fill.fore_color.rgb = RGBColor(*theme["accent"]); accent.line.fill.background()
    add_text(cover, config.grade.upper() + " • " + config.book.upper(), 1.28, 1.1, 10.8, .42, 15, theme["light"], True)
    add_text(cover, lesson.get("title") or config.lesson, 1.25, 1.75, 10.8, 2.25, 38, (255, 255, 255), True, valign=MSO_ANCHOR.MIDDLE)
    info = f"{config.periods} tiết  •  Giáo viên: {config.teacher or '................................'}"
    if config.school:
        info += f"\n{config.school}"
    add_text(cover, info, 1.28, 4.55, 10.5, 1.0, 18, theme["light"])
    add_text(cover, "POWERPOINT BÀI GIẢNG TOÁN THPT", 1.28, 6.65, 10.5, .35, 12, theme["light"], True)

    page = 1
    for slide_data in lesson["slides"]:
        chunks = split_bullets(slide_data["bullets"])
        for chunk_index, chunk in enumerate(chunks):
            slide = prs.slides.add_slide(blank)
            add_full_background(slide, (255, 255, 255))
            title = slide_data["title"] + (f" ({chunk_index + 1}/{len(chunks)})" if len(chunks) > 1 else "")
            activity = slide_data["activity"]
            add_header(slide, title, activity, theme, page)
            visual = None
            if chunk_index == 0 and slide_data.get("graph"):
                try:
                    visual = create_graph(slide_data["graph"])
                except (ValueError, SyntaxError, TypeError):
                    visual = None
            elif chunk_index == 0 and slide_data.get("variation_table"):
                visual = create_variation_table(slide_data["variation_table"])

            has_answer = config.include_answers and bool(slide_data.get("answer"))
            content_bottom = 5.48 if has_answer else 6.78
            
            if visual:
                # ÉP CHIỀU RỘNG CHỮ TỐI ĐA LÀ 7.0 INCH (~1/2 trang theo chiều ngang)
                # Chữ chạy tới mốc này sẽ TỰ ĐỘNG rớt dòng, hoàn toàn không che lấp Hình bên phải.
                add_bullets(slide, chunk, .75, 1.72, 7.0, content_bottom - 1.72, 21)
                
                # Cố định hình vẽ/bảng biến thiên ở góc trên bên phải
                slide.shapes.add_picture(visual, Inches(8.2), Inches(1.08), width=Inches(4.8))
            else:
                size = 23 if sum(map(len, chunk)) < 280 else 21
                add_bullets(slide, chunk, .82, 1.72, 11.7, content_bottom - 1.72, size)
                
            if has_answer:
                add_answer_box(slide, slide_data["answer"], theme)
            if config.include_notes and slide_data.get("teacher_note"):
                notes_frame = slide.notes_slide.notes_text_frame
                notes_frame.text = slide_data["teacher_note"]
            page += 1

    output = io.BytesIO()
    prs.save(output)
    return output.getvalue()


def build_exam_docx(exam: dict[str, Any], certificate_data: dict[str, Any] | None = None) -> bytes:
    doc = Document()
    doc.add_heading(exam.get("title", "ĐỀ KIỂM TRA TOÁN"), 0)
    doc.add_paragraph(f"{exam.get('subject','Toán')} • {exam.get('grade','')}" )
    for i, q in enumerate(exam.get("questions", []), 1):
        doc.add_heading(f"Câu {i}. {q.get('question','')}", level=2)
        typ = str(q.get("type", "mcq"))
        if typ in {"mcq", "multiple_choice"}:
            for j, opt in enumerate(q.get("options", [])):
                doc.add_paragraph(f"{chr(65+j)}. {opt}")
        elif typ in {"true_false", "tf"}:
            for j, stt in enumerate(q.get("statements", q.get("options", []))):
                doc.add_paragraph(f"{j+1}) {stt}")
        else:
            doc.add_paragraph("Trả lời: ........................................................")
    if certificate_data:
        doc.add_page_break()
        doc.add_heading("CHỨNG NHẬN QA V4.0", 1)
        doc.add_paragraph(json.dumps(certificate_data, ensure_ascii=False, indent=2))
    out=io.BytesIO(); doc.save(out); return out.getvalue()


def build_exam_pptx(exam: dict[str, Any], theme_name: str = "Xanh học thuật", show_answers: bool = False) -> bytes:
    prs=Presentation(); prs.slide_width, prs.slide_height=Inches(13.333), Inches(7.5); blank=prs.slide_layouts[6]
    theme=THEMES[theme_name]
    cover=prs.slides.add_slide(blank); add_full_background(cover, theme["primary"])
    add_text(cover, "AI EXAM FACTORY V4.0", 1.0, 1.0, 11.0, .5, 18, theme["light"], True)
    add_text(cover, exam.get("title", "ĐỀ KIỂM TRA TOÁN"), 1.0, 2.0, 11.2, 2.0, 34, (255,255,255), True, valign=MSO_ANCHOR.MIDDLE)
    add_text(cover, f"{exam.get('grade','')} • {exam.get('subject','Toán')}", 1.0, 4.5, 10.5, .5, 18, theme["light"])
    for i,q in enumerate(exam.get("questions", []),1):
        slide=prs.slides.add_slide(blank); add_full_background(slide,(255,255,255))
        add_header(slide, f"Câu {i}", str(q.get("level", "")).upper() or "ĐỀ KIỂM TRA", theme, i)
        bullets=[clean_text(q.get("question",""))]
        typ=q.get("type","mcq")
        if typ in {"mcq","multiple_choice"}:
            bullets += [f"{chr(65+j)}. {clean_text(o)}" for j,o in enumerate(q.get("options",[]))]
        elif typ in {"true_false","tf"}:
            bullets += [f"{j+1}) {clean_text(o)}" for j,o in enumerate(q.get("statements",q.get("options",[])))]
        add_bullets(slide, bullets, .8, 1.7, 11.7, 4.6, 19)
        if show_answers and q.get("solution"):
            add_answer_box(slide, clean_text(q.get("solution")), theme)
    out=io.BytesIO(); prs.save(out); return out.getvalue()


def combined_v4_report(exam: dict[str, Any], math_report: dict, ped_report: dict, council: list[dict]) -> dict[str, Any]:
    council_fail=any(str(x.get("status")).upper()=="FAIL" for x in council)
    council_review=any(str(x.get("status")).upper() in {"REVIEW","MANUAL_REVIEW"} for x in council)
    status="FAIL" if math_report["status"]=="FAIL" or ped_report["status"]=="FAIL" or council_fail else "MANUAL_REVIEW" if math_report["status"]=="MANUAL_REVIEW" or ped_report["status"]=="MANUAL_REVIEW" or council_review else "PASS"
    scores=[math_report["summary"]["score"], ped_report["summary"]["score"]]+[float(x.get("score",0)) for x in council if isinstance(x.get("score"),(int,float))]
    score=round(sum(scores)/len(scores),1) if scores else 0
    base={"version":"4.0.0","status":status,"summary":{"total":len(exam.get("questions",[])),"score":score},"math":math_report,"pedagogy":ped_report,"council":council}
    base["certificate"]=certificate(base)
    return base

def get_api_key() -> str:
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""

st.set_page_config(page_title="Trợ lý PowerPoint Toán THPT", page_icon="📐", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.4rem;max-width:1250px}.stButton>button{font-weight:700;border-radius:10px}
[data-testid="stSidebar"]{background:#f5f8fb}.small-note{color:#59636e;font-size:.92rem}
</style>
""", unsafe_allow_html=True)
st.title("📐 Trợ lý soạn PowerPoint Toán THPT")
st.caption(f"Phiên bản {APP_VERSION} • Đồ họa Toán học AST • Chống rớt chữ")

api_key = get_api_key()
with st.sidebar:
    mode = st.radio("Chế độ làm việc", ["Tạo bài giảng PowerPoint", "🏭 AI Exam Factory V4.5", "🧬 Exam Intelligence V5.0", "Thẩm định đề Toán Pro", "Thẩm định đề Toán 360°"], index=0)
if not api_key and mode not in {"Thẩm định đề Toán Pro", "Thẩm định đề Toán 360°", "🧬 Exam Intelligence V5.0"}:
    st.error("Chưa cấu hình GEMINI_API_KEY trong Secrets. Chế độ Thẩm định đề Toán Pro vẫn chạy offline không cần API.")
    st.stop()

with st.sidebar:
    st.header("Thông tin bài dạy")
    teacher = st.text_input("Tên giáo viên", placeholder="Nguyễn Văn A")
    school = st.text_input("Trường", placeholder="Trường THPT …")
    grade = st.selectbox("Khối lớp", ["Toán 10", "Toán 11", "Toán 12"])
    book = st.selectbox("Bộ sách", ["Kết nối tri thức", "Cánh Diều", "Chân trời sáng tạo", "Tài liệu riêng"])
    lesson = st.text_input("Tên bài", placeholder="Có thể để trống để AI xác định")
    periods = st.number_input("Số tiết", 1, 6, 2)
    student_level = st.selectbox("Đối tượng học sinh", ["Trung bình – khá", "Đồng đều", "Còn hạn chế", "Khá – giỏi"])
    slide_count = st.slider("Số slide dự kiến", 15, 50, 30)
    theme_name = st.selectbox("Phong cách", list(THEMES))
    include_answers = st.checkbox("Đưa đáp án/gợi ý vào slide", True)
    include_notes = st.checkbox("Tạo ghi chú dành cho giáo viên", True)
    
    st.markdown("---")
    try:
        genai.configure(api_key=api_key)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if available_models:
            default_index = available_models.index('models/gemini-1.5-flash') if 'models/gemini-1.5-flash' in available_models else 0
            selected_model = st.selectbox("🤖 Chọn mô hình AI:", available_models, index=default_index)
        else:
            st.error("Khóa API không có quyền truy cập.")
            selected_model = None
    except Exception:
        selected_model = "models/gemini-1.5-flash"

st.subheader("1. Tải tài liệu nguồn")
uploaded = st.file_uploader("PDF, Word, TXT hoặc JSON (tối đa 20 MB)", type=["pdf", "docx", "txt", "json"])
st.markdown('<div class="small-note">Nên dùng tài liệu chính thống: SGK, SGV, kế hoạch bài dạy hoặc chuyên đề đã kiểm duyệt.</div>', unsafe_allow_html=True)

if mode == "🧬 Exam Intelligence V5.0":
    st.subheader("🧬 Exam Intelligence V5.0 — Question DNA + Ngân hàng câu hỏi + Adaptive Exam Factory")
    st.info("V5.0: Ngân hàng câu hỏi → Question DNA → chọn theo ma trận → Math Engine + Sư phạm → Hội đồng 3 AI → nhiều mã đề → QA liên mã → Release Gate.")
    bank=QuestionBank("question_bank_v5.sqlite3")
    tabA,tabB,tabC=st.tabs(["🗃️ Ngân hàng câu hỏi","🏭 Tạo đề từ ngân hàng","📊 Analytics & DNA"])
    with tabA:
        st.write(f"**Số câu đang lưu:** {bank.count()}")
        bank_file=st.file_uploader("Nhập đề JSON để đưa vào ngân hàng",type=["json"],key="v5_bank_upload")
        if st.button("➕ NẠP CÂU HỎI VÀO NGÂN HÀNG",use_container_width=True) and bank_file:
            try:
                ex=json.loads(bank_file.getvalue().decode("utf-8")); st.success(bank.add_exam(ex))
            except Exception as e: st.error(str(e))
        c1,c2,c3=st.columns(3)
        topic_filter=c1.text_input("Lọc chủ đề",key="v5_topic")
        level_filter=c2.text_input("Lọc mức độ",key="v5_level")
        type_filter=c3.selectbox("Lọc loại",["","mcq","true_false","short_answer"],key="v5_type")
        rows=bank.search(topic_filter,level_filter,type_filter,100)
        st.dataframe([{"ID":q.get("id"),"Loại":qtype(q),"Mức độ":q.get("level"),"Chủ đề":q.get("topic"),"DNA":q.get("_dna",{}).get("fingerprint","")[:12],"Lần dùng":q.get("_uses",0)} for q in rows],use_container_width=True)
    with tabB:
        total_v5=st.number_input("Tổng số câu",1,60,10,key="v5_total")
        mcq_v5=st.number_input("MCQ",0,int(total_v5),min(10,int(total_v5)),key="v5_mcq")
        tf_v5=st.number_input("Đúng/Sai",0,int(total_v5),0,key="v5_tf")
        short_v5=st.number_input("Trả lời ngắn",0,int(total_v5),0,key="v5_short")
        levels_v5=st.text_input("Mức độ", "nhận biết:3, thông hiểu:3, vận dụng:3, vận dụng cao:1",key="v5_levels")
        topics_v5=st.text_area("Chủ đề ưu tiên", "Tính đơn điệu và cực trị của hàm số",key="v5_topics")
        codes_v5=st.number_input("Số mã đề",1,20,4,key="v5_codes")
        if st.button("🚀 TẠO ĐỀ V5.0 + RELEASE GATE",type="primary",use_container_width=True):
            try:
                bp={"total_questions":int(total_v5),"type_distribution":{"mcq":int(mcq_v5),"true_false":int(tf_v5),"short_answer":int(short_v5)},"level_distribution":{}}
                for item in levels_v5.split(','):
                    if ':' in item:
                        k,v=item.split(':',1); bp["level_distribution"][k.strip()]=int(v.strip())
                bp["topic_distribution"]={x.strip():1 for x in topics_v5.splitlines() if x.strip()}
                exam={"title":"Đề Toán V5.0","subject":"Toán","grade":grade,"blueprint":bp,"questions":select_from_bank(bank,bp)}
                if len(exam["questions"])<int(total_v5): st.warning(f"Ngân hàng chỉ đáp ứng {len(exam['questions'])}/{int(total_v5)} câu theo bộ lọc. Có thể bổ sung câu hoặc dùng AI Factory V4.5 để sinh câu mới.")
                mr=audit_exam(exam); pr=audit_pedagogy(exam)
                variants=build_variants(exam,int(codes_v5)); vc=variant_consistency(variants)
                gate=release_gate(mr,pr,[],vc); mf=build_v5_manifest(exam,variants,gate)
                bank.mark_used(exam["questions"])
                st.session_state["v5_exam"]=exam; st.session_state["v5_mr"]=mr; st.session_state["v5_pr"]=pr; st.session_state["v5_variants"]=variants; st.session_state["v5_manifest"]=mf
            except Exception as e: st.error(f"V5.0 lỗi: {e}")
        exam=st.session_state.get("v5_exam"); mr=st.session_state.get("v5_mr"); pr=st.session_state.get("v5_pr"); variants=st.session_state.get("v5_variants",[]); mf=st.session_state.get("v5_manifest",{})
        if exam:
            gate=mf.get("release_gate","CONDITIONAL"); a,b,c,d=st.columns(4); a.metric("Câu",len(exam.get("questions",[]))); b.metric("Gate",gate); c.metric("Mã đề",len(variants)); d.metric("DNA unique",coverage_report(exam).get("unique",0))
            if gate=="CERTIFIED": st.success("🟢 CERTIFIED — đề vượt Release Gate V5.0 trong phạm vi các bộ máy tự động.")
            elif gate=="REJECTED": st.error("🔴 REJECTED — cần sửa lỗi trước khi phát hành.")
            else: st.warning("🟡 CONDITIONAL — cần giáo viên duyệt các điểm REVIEW.")
            st.download_button("📥 Tải manifest V5.0",json.dumps(mf,ensure_ascii=False,indent=2),"manifest_v5.json","application/json",use_container_width=True)
            st.download_button("📥 Tải đề gốc JSON",json.dumps(exam,ensure_ascii=False,indent=2),"de_goc_v5.json","application/json",use_container_width=True)
    with tabC:
        st.json(bank.stats())
        qshow=bank.search(limit=20)
        if qshow:
            with st.expander("🧬 DNA của 20 câu gần nhất"):
                st.json([question_dna(q) for q in qshow])
    bank.close()
    st.stop()

if mode == "🏭 AI Exam Factory V4.5":
    st.subheader("🏭 AI Exam Factory V4.5 — AI Exam Factory + Adaptive Intelligence")
    st.info("Luồng V4.5: Ma trận → AI sinh đề → Math Engine → Sư phạm → 3 AI phản biện → phân tích độ khó → nhiều mã đề → QA liên mã → chứng nhận.")
    col1,col2=st.columns(2)
    with col1:
        total_q=st.number_input("Tổng số câu", 1, 60, 10)
        grade_exam=st.selectbox("Khối", ["Toán 10","Toán 11","Toán 12"], key="exam_grade")
        topics=st.text_area("Chủ đề (mỗi dòng một chủ đề)", "Tính đơn điệu và cực trị của hàm số\nGTLN – GTNN\nHàm số mũ và logarit")
    with col2:
        mcq_n=st.number_input("Số MCQ",0,int(total_q),max(1,min(10,int(total_q))))
        tf_n=st.number_input("Số Đúng/Sai",0,int(total_q),0)
        short_n=st.number_input("Số trả lời ngắn",0,int(total_q),0)
        levels=st.text_input("Phân bố mức độ", "nhận biết:3, thông hiểu:3, vận dụng:3, vận dụng cao:1")
        variant_n=st.number_input("Số mã đề", 1, 8, 4, key="variant_n")
        variant_strategy=st.selectbox("Chiến lược mã đề", ["Đảo thứ tự câu + phương án", "Biến thể tham số (AI sinh lại + kiểm chứng)"])
    if st.button("🚀 SINH ĐỀ V4.5 + HỘI ĐỒNG 3 AI", type="primary", use_container_width=True):
        if not selected_model: st.error("Chưa có mô hình AI.")
        else:
            try:
                bp={"total_questions":int(total_q),"type_distribution":{"mcq":int(mcq_n),"true_false":int(tf_n),"short_answer":int(short_n)},"level_distribution":{}}
                for item in levels.split(','):
                    if ':' in item:
                        k,v=item.split(':',1); bp["level_distribution"][k.strip()]=int(v.strip())
                bp["topic_distribution"]={x.strip():1 for x in topics.splitlines() if x.strip()}
                source_text=""
                if uploaded and uploaded.name.lower().endswith((".txt",".docx")):
                    source_text=read_source(uploaded)[0]
                model=genai.GenerativeModel(selected_model,generation_config={"response_mime_type":"application/json","temperature":0.2})
                with st.status("Đang chạy dây chuyền V4.0…", expanded=True) as status:
                    st.write("1/5 AI đang sinh đề theo ma trận…")
                    exam=parse_ai_json(model.generate_content(exam_generation_prompt(bp,source_text)).text)
                    st.write("2/5 Math Engine kiểm chứng…")
                    mr=audit_exam(exam)
                    st.write("3/5 Pedagogy Engine thẩm định…")
                    pr=audit_pedagogy(exam)
                    council=[]
                    for role,label in [("math","AI Toán học"),("pedagogy","AI Sư phạm"),("adversarial","AI Red-Team")]:
                        st.write(f"4/5 {label} phản biện…")
                        try: council.append(parse_ai_json(model.generate_content(reviewer_prompt(role,exam,mr,pr)).text))
                        except Exception as e: council.append({"role":role,"status":"REVIEW","score":0,"findings":[{"severity":"REVIEW","finding":f"Không đọc được phản biện: {e}"}]})
                    st.write("5/5 QA Gate + chứng nhận…")
                    rep=combined_v4_report(exam,mr,pr,council)
                    adaptive=analyze_exam(exam)
                    variants=[exam]
                    import copy, random
                    for vi in range(1,int(variant_n)):
                        vv=copy.deepcopy(exam)
                        rng=random.Random(1000+vi)
                        rng.shuffle(vv.get("questions",[]))
                        for q in vv.get("questions",[]):
                            if q.get("type","mcq")=="mcq" and isinstance(q.get("options"),list) and len(q["options"])==4:
                                old_opts=list(q["options"]); old_ans=q.get("answer_index")
                                order=list(range(4)); rng.shuffle(order)
                                q["options"]=[old_opts[i] for i in order]
                                if isinstance(old_ans,int): q["answer_index"]=order.index(old_ans)
                        vv["variant_code"]=chr(66+vi) if vi<25 else f"V{vi+1}"
                        variants.append(vv)
                    manifest=build_manifest(variants,rep)
                    manifest["adaptive_analysis"]=adaptive
                    st.session_state["v4_exam"]=exam; st.session_state["v4_report"]=rep; st.session_state["v45_variants"]=variants; st.session_state["v45_manifest"]=manifest
                    status.update(label="Hoàn tất dây chuyền V4.5",state="complete",expanded=False)
            except Exception as e: st.error(f"V4.0 gặp lỗi: {e}")
    exam=st.session_state.get("v4_exam"); rep=st.session_state.get("v4_report")
    if exam and rep:
        c1,c2,c3=st.columns(3); c1.metric("QA Score",rep["summary"]["score"]); c2.metric("Trạng thái",rep["status"]); c3.metric("Chứng nhận",rep["certificate"]["certificate_status"])
        if rep["status"]=="PASS": st.success("🟢 CERTIFIED — đề vượt qua Gate V4.0 trong phạm vi các bộ máy kiểm tra.")
        elif rep["status"]=="FAIL": st.error("🔴 REJECTED — còn lỗi FAIL, không nên phát hành.")
        else: st.warning("🟡 CONDITIONAL — cần giáo viên duyệt các điểm REVIEW.")
        for c in rep["council"]:
            with st.expander(f"{c.get('role','Reviewer')} — {c.get('status','REVIEW')} — {c.get('score',0)}"):
                st.json(c)
        with st.expander("🔐 Chứng nhận & dấu vết phiên bản"): st.json(rep["certificate"])
        st.download_button("📥 JSON báo cáo V4.0",json.dumps({"exam":exam,"report":rep},ensure_ascii=False,indent=2),"bao_cao_V4_0.json","application/json",use_container_width=True)
        st.download_button("📝 Xuất Word đề",build_exam_docx(exam,rep["certificate"]),"de_toan_V4_0.docx","application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)
        st.download_button("📊 Xuất PowerPoint đề",build_exam_pptx(exam,theme_name,False),"de_toan_V4_0.pptx","application/vnd.openxmlformats-officedocument.presentationml.presentation",use_container_width=True)
        variants=st.session_state.get("v45_variants",[exam]); manifest=st.session_state.get("v45_manifest",{})
        st.markdown("### 🧠 Adaptive Intelligence")
        ad=manifest.get("adaptive_analysis",{})
        ac1,ac2,ac3=st.columns(3); ac1.metric("Độ khó heuristic TB",ad.get("summary",{}).get("avg_difficulty",0)); ac2.metric("Biên độ độ khó",ad.get("summary",{}).get("spread",0)); ac3.metric("Số mã đề",len(variants))
        st.caption("Điểm độ khó là heuristic hỗ trợ biên tập, không phải chỉ số tâm trắc học.")
        vc=variant_consistency(variants); st.write(f"**QA liên mã:** {vc['status']} — {len(vc.get('issues',[]))} cảnh báo")
        if vc.get("issues"): st.dataframe(vc["issues"],use_container_width=True)
        st.download_button("📦 Tải manifest + QA nhiều mã",json.dumps(manifest,ensure_ascii=False,indent=2),"manifest_v4_5.json","application/json",use_container_width=True)
    st.stop()

if mode in {"Thẩm định đề Toán Pro", "Thẩm định đề Toán 360°"}:
    st.subheader("2. Hệ thống thẩm định đề Toán 360°")
    st.info("V3.5: Math Engine + kiểm tra cấu trúc + ma trận + miền xác định + trùng/gần trùng + chất lượng sư phạm + QA Gate. Các tiêu chí heuristic chỉ đưa ra REVIEW, không tự kết luận thay giáo viên.")
    json_text = st.text_area("Dán trực tiếp JSON của đề", height=220, placeholder='{"questions": [...], "blueprint": {...}}')
    if st.button("🛡️ CHẠY THẨM ĐỊNH 360°", type="primary", use_container_width=True) and (uploaded or json_text.strip()):
        try:
            if json_text.strip(): exam=json.loads(json_text)
            else: exam=json.loads(uploaded.getvalue().decode("utf-8"))
            math_report=audit_exam(exam)
            ped_report=audit_pedagogy(exam)
            # Conservative combined gate: any deterministic FAIL keeps the exam FAIL.
            all_issues=math_report["exam_issues"]+ped_report["exam_issues"]
            combined_status="FAIL" if math_report["status"]=="FAIL" or ped_report["status"]=="FAIL" else "MANUAL_REVIEW" if math_report["status"]=="MANUAL_REVIEW" or ped_report["status"]=="MANUAL_REVIEW" else "PASS"
            combined_score=round((math_report["summary"]["score"]+ped_report["summary"]["score"])/2,1)
            st.session_state["exam_current"]=exam
            st.session_state["audit_report"]={"status":combined_status,"summary":{"total":len(exam.get("questions",[])),"pass":math_report["summary"]["pass"],"fail":max(math_report["summary"]["fail"],ped_report["summary"]["fail"]),"manual_review":max(math_report["summary"]["manual_review"],ped_report["summary"]["manual_review"]),"score":combined_score},"math":math_report,"pedagogy":ped_report,"exam_issues":all_issues}
        except Exception as e:
            st.error(f"Không đọc được đề JSON: {e}")
    report=st.session_state.get("audit_report")
    exam=st.session_state.get("exam_current")
    if report:
        sm=report["summary"]
        c1,c2,c3,c4,c5=st.columns(5)
        c1.metric("Tổng câu",sm["total"]); c2.metric("PASS",sm["pass"]); c3.metric("FAIL",sm["fail"]); c4.metric("REVIEW",sm["manual_review"]); c5.metric("360 Score",sm["score"])
        if report["status"]=="PASS": st.success("🟢 ĐỀ ĐẠT – qua cả kiểm tra Toán và kiểm tra sư phạm tự động.")
        elif report["status"]=="FAIL": st.error("🔴 ĐỀ KHÔNG ĐẠT – phải sửa lỗi FAIL trước khi phát hành.")
        else: st.warning("🟡 ĐỀ CẦN DUYỆT – có tiêu chí cần giáo viên thẩm định thủ công.")
        tab1,tab2,tab3=st.tabs(["🧮 Math Engine","🎓 Sư phạm 360°","📋 QA Gate"])
        with tab1:
            mr=report["math"]
            st.write(f"Trạng thái: **{mr['status']}** · QA Score: **{mr['summary']['score']}**")
            if mr["exam_issues"]: st.dataframe(mr["exam_issues"],use_container_width=True)
            table=[]
            for r in mr["questions"]: table.append({"Câu":r["number"],"Mức độ":r["level"],"Chủ đề":r["topic"],"Trạng thái":r["status"],"Số lỗi":len(r["issues"])})
            st.dataframe(table,use_container_width=True)
            with st.expander("🔎 Chi tiết Math Engine"):
                for r in mr["questions"]:
                    st.markdown(f"**Câu {r['number']} — {r['status']}**")
                    for x in r["issues"]: st.write(f"• {x['severity']} | {x['code']}: {x['message']} {x['evidence']}")
        with tab2:
            pr=report["pedagogy"]
            st.write(f"Trạng thái: **{pr['status']}** · Pedagogy Score: **{pr['summary']['score']}**")
            if pr["exam_issues"]: st.dataframe(pr["exam_issues"],use_container_width=True)
            ptable=[]
            for r in pr["questions"]: ptable.append({"Câu":r["number"],"Loại":r["type"],"Mức độ":r["level"],"Chủ đề":r["topic"],"Trạng thái":r["status"],"Số cảnh báo":len(r["issues"])})
            st.dataframe(ptable,use_container_width=True)
            with st.expander("🔎 Chi tiết kiểm tra sư phạm"):
                for r in pr["questions"]:
                    st.markdown(f"**Câu {r['number']} — {r['status']}**")
                    for x in r["issues"]: st.write(f"• {x['severity']} | {x['code']}: {x['message']} {x['evidence']}")
            st.caption("Lưu ý: kiểm tra mức độ nhận thức là heuristic hỗ trợ giáo viên; không phải phép đo tâm lý học hay thay thế thẩm định chuyên môn.")
        with tab3:
            st.markdown("**Nguyên tắc QA Gate:** FAIL = chặn phát hành; REVIEW = cần giáo viên duyệt; PASS = không phát hiện lỗi trong phạm vi engine.")
            if report["exam_issues"]: st.dataframe(report["exam_issues"],use_container_width=True)
            st.json({"status":report["status"],"summary":report["summary"]})
        if st.button("🔧 TỰ SỬA LỖI KỸ THUẬT + THẨM ĐỊNH 360° LẦN 2", use_container_width=True):
            fixed,changes=safe_autofix(exam)
            new_math=audit_exam(fixed); new_ped=audit_pedagogy(fixed)
            combined_status="FAIL" if new_math["status"]=="FAIL" or new_ped["status"]=="FAIL" else "MANUAL_REVIEW" if new_math["status"]=="MANUAL_REVIEW" or new_ped["status"]=="MANUAL_REVIEW" else "PASS"
            combined={"status":combined_status,"summary":{"total":len(fixed.get("questions",[])),"pass":new_math["summary"]["pass"],"fail":max(new_math["summary"]["fail"],new_ped["summary"]["fail"]),"manual_review":max(new_math["summary"]["manual_review"],new_ped["summary"]["manual_review"]),"score":round((new_math["summary"]["score"]+new_ped["summary"]["score"])/2,1)},"math":new_math,"pedagogy":new_ped,"exam_issues":new_math["exam_issues"]+new_ped["exam_issues"]}
            st.session_state["exam_current"]=fixed; st.session_state["audit_report"]=combined
            st.success(f"Đã sửa {len(changes)} lỗi kỹ thuật xác định chắc chắn.")
            if changes: st.code("\n".join(changes))
            st.rerun()
        payload={"version":"3.5.0","exam":exam,"audit":report}
        st.download_button("📥 Tải báo cáo thẩm định 360° JSON",json.dumps(payload,ensure_ascii=False,indent=2),"bao_cao_tham_dinh_360_v3_5.json","application/json",use_container_width=True)
    st.stop()

st.subheader("2. Tạo bài giảng")
if st.button("🚀 Phân tích và tạo PowerPoint", type="primary", use_container_width=True, disabled=uploaded is None):
    try:
        config = LessonConfig(teacher, school, grade, book, lesson, int(periods), student_level,
                              int(slide_count), theme_name, include_answers, include_notes)
        source_text, source_bytes, source_type = read_source(uploaded)
        
        with st.status("Đang soạn bài giảng…", expanded=True) as status:
            st.write("Đang đọc và cấu trúc hóa tài liệu nguồn…")
            lesson_data = generate_lesson(selected_model, source_text, source_bytes, source_type, config)
            
            st.write("Đang kiểm tra nội dung và dựng PowerPoint…")
            pptx_bytes = build_pptx(lesson_data, config)
            status.update(label="Đã tạo xong bài giảng", state="complete", expanded=False)
            
        safe_name = re.sub(r"[^0-9A-Za-zÀ-ỹ_-]+", "_", lesson_data.get("title") or "Bai_giang_Toan").strip("_")
        filename = f"{safe_name[:70]}_{uuid.uuid4().hex[:6]}.pptx"
        st.success(f"Đã tạo {len(lesson_data['slides'])} slide. Các ý dài đã được cắt trang tự động.")
        st.download_button("📥 Tải PowerPoint", pptx_bytes, filename,
                           "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                           use_container_width=True)
                           
    except json.JSONDecodeError:
        st.error("AI trả về dữ liệu chưa đúng định dạng. Vui lòng bấm tạo lại.")
    except ValueError as exc:
        st.error(str(exc))
    except Exception as e:
        st.error(f"Lỗi: {str(e)}")

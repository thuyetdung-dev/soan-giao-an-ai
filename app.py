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

APP_VERSION = "2.0.1 (Hybrid Stable)"
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
    replacements = {"<=>": "⇔", "=>": "⇒", ">=": "≥", "<=": "≤", "+-": "±"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    superscripts = str.maketrans("0123456789-+", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺")
    subscripts = str.maketrans("0123456789-+", "₀₁₂₃₄₅₆₇₈₉₋₊")
    text = re.sub(r"\^\{?(-?\d+)\}?", lambda m: m.group(1).translate(superscripts), text)
    text = re.sub(r"_\{?(-?\d+)\}?", lambda m: m.group(1).translate(subscripts), text)
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
- Đối tượng: {config.student_level}; Số slide dự kiến: {config.slide_count}
Mỗi slide có tối đa 6 gạch đầu dòng ngắn gọn. {answer_rule}
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
    "teacher_note":"",
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
    p.text = clean_text(text)
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
    frame.clear(); frame.word_wrap = True
    frame.margin_left = Inches(.08); frame.margin_right = Inches(.08)
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
                add_bullets(slide, chunk, .75, 1.72, 5.35, content_bottom - 1.72, 19)
                slide.shapes.add_picture(visual, Inches(6.28), Inches(1.72), width=Inches(6.15), height=Inches(4.65))
            else:
                size = 23 if sum(map(len, chunk)) < 280 else 19
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
st.caption(f"Phiên bản {APP_VERSION} • Đồ họa Toán học AST • Kết nối API Tối ưu")

api_key = get_api_key()
if not api_key:
    st.error("Chưa cấu hình GEMINI_API_KEY trong Secrets. Xem tệp README để thiết lập.")
    st.stop()

# KHÔI PHỤC MENU CHỌN MÔ HÌNH THÔNG MINH BÊN TRÁI
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
    # Menu AI Tự Động Quét Khóa
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
uploaded = st.file_uploader("PDF, Word hoặc TXT (tối đa 20 MB)", type=["pdf", "docx", "txt"])
st.markdown('<div class="small-note">Nên dùng tài liệu chính thống: SGK, SGV, kế hoạch bài dạy hoặc chuyên đề đã kiểm duyệt.</div>', unsafe_allow_html=True)

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

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
matplotlib.use('Agg')
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

try:
    import sympy as sp
except Exception:
    sp = None

APP_VERSION = '3.1.0 (AI Exam + Math Verification + Interactive PPT)'
MAX_UPLOAD_MB = 20
MAX_SOURCE_CHARS = 100_000
MAX_SLIDES = 100
MAX_QUESTIONS = 40

THEMES = {
    'Xanh học thuật': {'primary': (16, 62, 105), 'accent': (31, 150, 180), 'light': (235, 246, 250)},
    'Xanh lá hiện đại': {'primary': (23, 92, 72), 'accent': (45, 166, 116), 'light': (235, 248, 242)},
    'Tím công nghệ': {'primary': (75, 53, 123), 'accent': (137, 99, 186), 'light': (245, 240, 251)},
    'Đỏ trang trọng': {'primary': (142, 32, 45), 'accent': (210, 76, 89), 'light': (253, 240, 242)},
    'Đen trắng tối giản': {'primary': (25, 25, 25), 'accent': (90, 90, 90), 'light': (242, 242, 242)},
}
ACTIVITY_COLORS = {
    'KHỞI ĐỘNG': (239, 108, 0), 'HÌNH THÀNH KIẾN THỨC': (21, 101, 192),
    'LUYỆN TẬP': (0, 130, 100), 'VẬN DỤNG': (126, 68, 153), 'CỦNG CỐ': (180, 45, 55),
}
ACTIVITIES = list(ACTIVITY_COLORS)

@dataclass
class LessonConfig:
    teacher: str; school: str; grade: str; book: str; lesson: str; periods: int
    student_level: str; slide_count: int; theme_name: str; include_answers: bool
    include_notes: bool; teaching_mode: str; exam_mode: str; interaction: bool
    source_priority: str; question_count: int; question_types: str

# ---------------- SOURCE ----------------
def clean_text(value: Any) -> str:
    text = str(value or '')
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('\\\\', '\\')
    replacements = {'<=>': '⇔', '=>': '⇒', '>=': '≥', '<=': '≤', '+-': '±'}
    for old, new in replacements.items(): text = text.replace(old, new)
    return text

def extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data)); parts = []
    for p in doc.paragraphs:
        if p.text.strip(): parts.append(p.text.strip())
    for i, table in enumerate(doc.tables, 1):
        parts.append(f'[BẢNG {i}]')
        for row in table.rows: parts.append(' | '.join(clean_text(c.text) for c in row.cells))
    return '\n'.join(parts)

def read_source(uploaded_file):
    data = uploaded_file.getvalue()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024: raise ValueError(f'Tệp vượt quá {MAX_UPLOAD_MB} MB.')
    name = uploaded_file.name.lower()
    if name.endswith('.docx'): return extract_docx(data)[:MAX_SOURCE_CHARS], data, 'docx'
    if name.endswith('.txt'): return data.decode('utf-8', errors='replace')[:MAX_SOURCE_CHARS], data, 'txt'
    if name.endswith('.pdf'): return '', data, 'pdf'
    raise ValueError('Chỉ hỗ trợ PDF, DOCX và TXT.')

# ---------------- SAFE MATH ENGINE ----------------
ALLOWED_FUNCTIONS = {'sin': np.sin, 'cos': np.cos, 'tan': np.tan, 'sqrt': np.sqrt, 'abs': np.abs,
                     'exp': np.exp, 'log': np.log, 'ln': np.log, 'asin': np.arcsin, 'acos': np.arccos, 'atan': np.arctan}
ALLOWED_CONSTANTS = {'pi': np.pi, 'e': np.e}
ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)
BINOP_FUNCS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
UNARY_FUNCS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def _check_math_ast(node):
    if isinstance(node, ast.Expression): _check_math_ast(node.body)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ALLOWED_BINOPS): _check_math_ast(node.left); _check_math_ast(node.right)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ALLOWED_UNARYOPS): _check_math_ast(node.operand)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS or node.keywords: raise ValueError('Hàm toán học không được hỗ trợ.')
        for arg in node.args: _check_math_ast(arg)
    elif isinstance(node, ast.Name):
        if node.id not in {'x', *ALLOWED_CONSTANTS}: raise ValueError(f"Biến '{node.id}' không được phép.")
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)): raise ValueError('Hằng số không hợp lệ.')
    else: raise ValueError('Biểu thức chứa thành phần không an toàn.')

def _evaluate_math_ast(node, scope):
    if isinstance(node, ast.Expression): return _evaluate_math_ast(node.body, scope)
    if isinstance(node, ast.BinOp): return BINOP_FUNCS[type(node.op)](_evaluate_math_ast(node.left, scope), _evaluate_math_ast(node.right, scope))
    if isinstance(node, ast.UnaryOp): return UNARY_FUNCS[type(node.op)](_evaluate_math_ast(node.operand, scope))
    if isinstance(node, ast.Call): return scope[node.func.id](*[_evaluate_math_ast(a, scope) for a in node.args])
    if isinstance(node, ast.Name): return scope[node.id]
    if isinstance(node, ast.Constant): return node.value
    raise ValueError('Không thể tính biểu thức.')

def safe_math_eval(expression: str, x: np.ndarray) -> np.ndarray:
    tree = ast.parse(expression.replace('^', '**').strip(), mode='eval'); _check_math_ast(tree)
    y = np.asarray(_evaluate_math_ast(tree, {'x': x, **ALLOWED_FUNCTIONS, **ALLOWED_CONSTANTS}), dtype=float)
    if y.ndim == 0: y = np.full_like(x, float(y))
    if y.shape != x.shape: raise ValueError('Biểu thức không tạo được y tương ứng với x.')
    return y

def normalize_sympy(expr: str):
    if sp is None: return None
    s = str(expr).replace('^', '**').replace('ln', 'log').replace('π', 'pi')
    try: return sp.sympify(s, locals={'x': sp.Symbol('x'), 'pi': sp.pi, 'e': sp.E, 'sqrt': sp.sqrt, 'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan, 'log': sp.log})
    except Exception: return None

def sympy_equal(a, b) -> bool:
    if sp is None: return False
    try: return bool(sp.simplify(a - b) == 0)
    except Exception: return False

def parse_number(v):
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(',', '.')
    try: return float(sp.N(sp.sympify(s))) if sp else float(s)
    except Exception: return None

def parse_solution_set(v):
    if isinstance(v, list): vals = v
    else:
        s = str(v).strip().replace('S=', '').replace('{', '').replace('}', '')
        vals = [z.strip() for z in s.split(',') if z.strip()]
    out=[]
    for z in vals:
        n=parse_number(z)
        if n is not None: out.append(n)
        elif sp:
            try: out.append(sp.N(sp.sympify(str(z).replace('^','**'))))
            except Exception: pass
    return out

def numeric_close(a,b,tol=1e-7):
    try: return abs(float(a)-float(b)) <= tol*max(1,abs(float(a)),abs(float(b)))
    except Exception: return False

# ---------------- INDEPENDENT QUESTION VERIFICATION ----------------
def verify_question(q: dict[str, Any]) -> dict[str, Any]:
    """The AI supplies machine-checkable metadata; expected answer is recomputed independently here."""
    result={'status':'MANUAL_REVIEW','ok':False,'method':'', 'expected':None, 'message':'Chưa có bộ kiểm chứng tự động.'}
    check=q.get('check') if isinstance(q.get('check'),dict) else {}
    ctype=str(check.get('type','')).lower().strip()
    answer_index=q.get('answer_index', q.get('answer', 0))
    try:
        if ctype == 'numeric_eval':
            f=normalize_sympy(check['expression']); xval=parse_number(check['x'])
            if f is None or xval is None: raise ValueError('Không đọc được biểu thức hoặc x.')
            expected=sp.N(f.subs(sp.Symbol('x'), xval)); candidate=q.get('expected_answer', check.get('expected_answer'))
            if candidate is None and isinstance(q.get('options'),list) and 0 <= int(answer_index) < len(q['options']): candidate=q['options'][int(answer_index)]
            candidate_num=parse_number(candidate)
            ok=numeric_close(expected,candidate_num)
            result.update(status='PASS' if ok else 'FAIL', ok=ok, method='SymPy thế giá trị', expected=str(expected), message='Đáp án khớp.' if ok else f'Đáp án AI khác kết quả tính lại: {expected}.')
        elif ctype == 'derivative':
            f=normalize_sympy(check['expression']); x=sp.Symbol('x'); candidate_raw=q.get('expected_answer', check.get('expected_answer'))
            if candidate_raw is None and isinstance(q.get('options'),list) and 0 <= int(answer_index) < len(q['options']): candidate_raw=q['options'][int(answer_index)]
            candidate=normalize_sympy(str(candidate_raw).replace('y\'','').replace('f\'',''))
            if f is None or candidate is None: raise ValueError('Không đọc được biểu thức đạo hàm.')
            expected=sp.diff(f,x); ok=sympy_equal(expected,candidate); result.update(status='PASS' if ok else 'FAIL', ok=ok, method='SymPy đạo hàm + rút gọn', expected=str(expected), message='Đạo hàm khớp.' if ok else f'Đạo hàm đúng là {sp.sstr(expected)}.')
        elif ctype == 'equation':
            lhs=normalize_sympy(check['lhs']); rhs=normalize_sympy(check['rhs']); x=sp.Symbol('x')
            if lhs is None or rhs is None: raise ValueError('Không đọc được phương trình.')
            expected=sp.solve(sp.Eq(lhs,rhs),x); candidate=q.get('expected_answer', check.get('expected_answer'))
            if candidate is None and isinstance(q.get('options'),list) and 0 <= int(answer_index) < len(q['options']): candidate=q['options'][int(answer_index)]
            got=parse_solution_set(candidate)
            expn=[float(sp.N(z)) for z in expected if getattr(z,'is_real',False) is not False]
            ok=len(expn)==len(got) and all(any(numeric_close(a,b) for b in got) for a in expn)
            result.update(status='PASS' if ok else 'FAIL', ok=ok, method='SymPy giải phương trình', expected=', '.join(map(str,expected)), message='Nghiệm khớp.' if ok else f'Nghiệm đúng: {expected}.')
        elif ctype == 'derivative_value':
            f=normalize_sympy(check['expression']); x=sp.Symbol('x'); xval=parse_number(check['x'])
            if f is None or xval is None: raise ValueError('Không đọc được dữ liệu.')
            expected=sp.diff(f,x).subs(x,xval); candidate=q.get('expected_answer', check.get('expected_answer'))
            if candidate is None and isinstance(q.get('options'),list) and 0 <= int(answer_index) < len(q['options']): candidate=q['options'][int(answer_index)]
            ok=numeric_close(expected,parse_number(candidate))
            result.update(status='PASS' if ok else 'FAIL', ok=ok, method='SymPy đạo hàm rồi thế x', expected=str(sp.N(expected)), message='Khớp.' if ok else f'Giá trị đúng: {sp.N(expected)}.')
        elif ctype == 'mcq_index':
            expected=int(check['correct_index']); got=int(answer_index)
            ok=expected==got; result.update(status='PASS' if ok else 'FAIL',ok=ok,method='Đối chiếu chỉ số đáp án',expected=str(expected),message='Khớp.' if ok else f'Chỉ số đúng: {expected}.')
        else:
            result['message']='Loại câu hỏi chưa có bộ kiểm chứng tự động; yêu cầu giáo viên duyệt.'
    except Exception as exc:
        result.update(status='ERROR',ok=False,message=f'Lỗi kiểm chứng: {exc}')
    return result

def verify_exam(exam):
    passed=failed=manual=0; rows=[]
    for i,q in enumerate(exam.get('questions',[])[:MAX_QUESTIONS],1):
        vr=verify_question(q); q['verification']=vr
        if vr['status']=='PASS': passed+=1
        elif vr['status']=='FAIL': failed+=1
        else: manual+=1
        rows.append({'Câu':i,'Mức độ':q.get('level',''),'Loại':q.get('type',''),'Trạng thái':vr['status'],'Phương pháp':vr['method'],'Kết quả engine':vr['message']})
    exam['qa_summary']={'pass':passed,'fail':failed,'manual':manual,'total':len(rows)}
    return exam,rows

# ---------------- AI ----------------
def build_prompt(config, source_text, exam=False):
    source_rule={'Chỉ dùng tài liệu nguồn':'Chỉ dùng nội dung có trong tài liệu nguồn. Nếu thiếu dữ kiện, ghi rõ.',
                  'Ưu tiên nguồn + kiến thức chuẩn':'Ưu tiên tài liệu nguồn; chỉ dùng kiến thức Toán chuẩn để lấp khoảng trống.',
                  'AI hỗ trợ mở rộng':'Dùng tài liệu nguồn làm trục chính, được phép mở rộng nhưng không trái chương trình.'}[config.source_priority]
    if exam:
        return f'''Bạn là chuyên gia ra đề Toán THPT theo GDPT 2018 và luyện thi TN.THPT.\nBối cảnh: khối={config.grade}; bộ sách={config.book}; chuyên đề={config.lesson}; mức độ={config.exam_mode}; đối tượng={config.student_level}; số câu={config.question_count}; loại câu={config.question_types}.\n{source_rule}\nTẠO JSON THUẦN, không markdown, theo schema:\n{{"title":"...","instructions":"...","questions":[{{"id":1,"type":"Trắc nghiệm 4 lựa chọn","level":"Nhận biết|Thông hiểu|Vận dụng|Vận dụng cao","question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"answer_index":0,"expected_answer":"...","solution":"...","check":{{"type":"numeric_eval","expression":"...","x":...}},"teacher_note":"..."}}]}}\nQUY TẮC BẮT BUỘC: answer_index luôn là chỉ số 0-3 của phương án đúng. expected_answer là giá trị/biểu thức toán học của phương án đúng để Math Engine kiểm tra độc lập. check phải là dữ liệu để chương trình tự tính lại. Với tính giá trị dùng numeric_eval + expression + x; với đạo hàm dùng derivative + expression; với phương trình dùng equation + lhs + rhs; với đạo hàm tại điểm dùng derivative_value + expression + x; nếu không thể máy kiểm chứng dùng mcq_index + correct_index. Không được tạo phương án mơ hồ hoặc nhiều đáp án đúng.\nTÀI LIỆU NGUỒN:\n{source_text[:MAX_SOURCE_CHARS]}''' 
    return f'''Bạn là chuyên gia thiết kế bài giảng PowerPoint Toán THPT theo GDPT 2018. Tạo bài giảng cho {config.lesson}, {config.grade}, {config.book}, {config.periods} tiết. Mục đích={config.teaching_mode}; mức độ={config.exam_mode}; đối tượng={config.student_level}; mục tiêu {config.slide_count} slide. {source_rule}\nTrả JSON thuần theo schema {{"title":"...","slides":[{{"title":"...","activity":"KHỞI ĐỘNG|HÌNH THÀNH KIẾN THỨC|LUYỆN TẬP|VẬN DỤNG|CỦNG CỐ","period":1,"bullets":["..."],"answer":"...","teacher_note":"...","question_type":"...","graph":{{"expression":"x**3-3*x","x_min":-4,"x_max":4}} ,"variation_table":{{"points":["-inf","-1","1","+inf"],"interval_signs":["+","-","+"],"values":["-inf","2","-2","+inf"]}}}}]}}. Chỉ thêm graph/variation_table khi dữ liệu chắc chắn.\nTÀI LIỆU NGUỒN:\n{source_text[:MAX_SOURCE_CHARS]}'''

def extract_json(raw):
    raw=raw.strip(); raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I|re.S).strip()
    try:return json.loads(raw)
    except Exception: pass
    m=re.search(r'\{.*\}',raw,re.S)
    if not m: raise ValueError('AI không trả về JSON hợp lệ.')
    return json.loads(m.group(0))

def generate_json(model_name, source_text, source_bytes, source_type, prompt):
    model=genai.GenerativeModel(model_name)
    contents=[prompt]
    if source_type=='pdf': contents=[{'mime_type':'application/pdf','data':source_bytes},prompt]
    response=model.generate_content(contents, generation_config={'temperature':0.1,'response_mime_type':'application/json'})
    return extract_json(response.text)

def normalize_exam(exam, count):
    if not isinstance(exam,dict) or not isinstance(exam.get('questions'),list): raise ValueError('AI không tạo đúng cấu trúc đề.')
    qs=[]
    for i,q in enumerate(exam['questions'][:count],1):
        if not isinstance(q,dict): continue
        q['id']=i; q['options']=[clean_text(x) for x in q.get('options',[])][:4]
        if len(q['options'])!=4: continue
        q['answer_index']=int(q.get('answer_index',q.get('answer',0)));
        if q['answer_index'] not in range(4): continue
        q['level']=clean_text(q.get('level','Thông hiểu')); q['type']=clean_text(q.get('type','Trắc nghiệm 4 lựa chọn'))
        qs.append(q)
    if not qs: raise ValueError('Không có câu hỏi hợp lệ.')
    exam['questions']=qs; return exam

# ---------------- GRAPHICS ----------------
def create_graph(graph):
    expr=str(graph.get('expression','x')); xmin=float(graph.get('x_min',-5)); xmax=float(graph.get('x_max',5))
    x=np.linspace(xmin,xmax,1600); y=safe_math_eval(expr,x); y[~np.isfinite(y)]=np.nan
    fig,ax=plt.subplots(figsize=(6.0,4.2)); ax.plot(x,y,linewidth=2); ax.axhline(0,linewidth=.8); ax.axvline(0,linewidth=.8); ax.grid(alpha=.2); ax.set_title('Đồ thị y = '+expr); fig.tight_layout()
    out=io.BytesIO(); fig.savefig(out,format='png',dpi=170); plt.close(fig); out.seek(0); return out

# ---------------- PPT HELPERS ----------------
def add_full_background(slide,color):
    shape=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,Inches(13.333),Inches(7.5)); shape.fill.solid(); shape.fill.fore_color.rgb=RGBColor(*color); shape.line.fill.background(); slide.shapes._spTree.remove(shape._element); slide.shapes._spTree.insert(2,shape._element)

def add_text(slide,text,left,top,width,height,size,color=(40,40,40),bold=False,align=PP_ALIGN.LEFT,valign=MSO_ANCHOR.TOP):
    box=slide.shapes.add_textbox(Inches(left),Inches(top),Inches(width),Inches(height)); f=box.text_frame; f.clear(); f.word_wrap=True; f.margin_left=f.margin_right=Inches(.08); f.margin_top=f.margin_bottom=Inches(.04); f.vertical_anchor=valign; p=f.paragraphs[0]; p.text=clean_text(text); p.alignment=align; p.font.name='Aptos'; p.font.size=Pt(size); p.font.bold=bold; p.font.color.rgb=RGBColor(*color); return box

def add_header(slide,title,theme,page,tag='POWERPOINT TOÁN THPT'):
    primary=theme['primary']; bar=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,Inches(13.333),Inches(.18)); bar.fill.solid(); bar.fill.fore_color.rgb=RGBColor(*primary); bar.line.fill.background()
    add_text(slide,title,.65,.38,11.6,.75,27,primary,True); add_text(slide,tag,.68,1.08,4.5,.3,10,theme['accent'],True); add_text(slide,str(page),12.25,7.05,.45,.25,10,(100,100,100),False,PP_ALIGN.RIGHT)

def add_button(slide,label,left,top,width,height,theme,target=None,font_size=20):
    sh=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(left),Inches(top),Inches(width),Inches(height)); sh.fill.solid(); sh.fill.fore_color.rgb=RGBColor(*theme['light']); sh.line.color.rgb=RGBColor(*theme['accent']); add_text(slide,label,left+.08,top+.12,width-.16,height-.18,font_size,theme['primary'],True,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE)
    if target is not None: sh.click_action.target_slide=target
    return sh

def add_cover(prs,title,config,theme):
    s=prs.slides.add_slide(prs.slide_layouts[6]); add_full_background(s,theme['primary']); add_text(s,config.grade.upper()+' • '+config.book.upper(),1.05,1.05,11,.4,15,theme['light'],True); add_text(s,title,1.05,1.65,11,2.2,38,(255,255,255),True,PP_ALIGN.LEFT,MSO_ANCHOR.MIDDLE); add_text(s,f'{config.lesson}\nGiáo viên: {config.teacher or "................................"}\n{config.school}',1.08,4.45,10.5,1.3,18,theme['light']); return s

def add_exam_interactive(prs,exam,config,theme,start_page):
    # Build question slides first, then feedback slides, and wire buttons after target slides exist.
    question_slides=[]; feedback_slides=[]
    for q in exam['questions']:
        qs=prs.slides.add_slide(prs.slide_layouts[6]); question_slides.append(qs)
        add_full_background(qs,(255,255,255)); add_header(qs,f"Câu {q['id']} • {q['level']}",theme,q['id']+start_page-1,'TƯƠNG TÁC • CHỌN ĐÁP ÁN')
        add_text(qs,q['question'],.7,1.55,11.9,1.7,24,theme['primary'],True)
        for i,opt in enumerate(q['options']):
            r,c=divmod(i,2); add_button(qs,opt,.8+c*6.1,3.55+r*1.25,5.65,.9,theme,None,17)
        add_text(qs,'Nhấp vào A/B/C/D để xem phản hồi.',.8,6.45,7,.35,11,(90,90,90))
        # create four feedback slides now
        for i in range(4):
            fs=prs.slides.add_slide(prs.slide_layouts[6]); feedback_slides.append((q, i, fs))
            correct=i==q.get('answer_index',0)
            add_full_background(fs,theme['light'] if correct else (250,245,245))
            add_header(fs,('✓ ĐÚNG' if correct else '✗ CHƯA ĐÚNG')+f' • Câu {q["id"]}',theme,0,'PHẢN HỒI TỨC THỜI')
            add_text(fs, 'Đáp án '+chr(65+q.get('answer',0))+'. '+q['options'][q.get('answer',0)],.8,1.55,11.5,1.0,24,theme['primary'],True)
            add_text(fs, ('Chính xác! Bạn có thể xem lời giải bên dưới.' if correct else 'Hãy thử lại và chú ý dữ kiện/điều kiện của bài.'),.8,2.7,11.5,.8,20)
            add_text(fs,'LỜI GIẢI / GỢI Ý\n'+str(q.get('solution','')), .8,3.65,11.5,1.8,18,theme['primary'],False)
            add_button(fs,'↩ Quay lại câu hỏi',4.5,6.15,4.3,.65,theme,qs,15)
    # Wire answer buttons: each q slide's shape order contains background/header/text then 4 buttons. Identify last four rounded rectangles.
    for idx,qs in enumerate(question_slides):
        q=exam['questions'][idx]
        targets=[feedback_slides[idx*4+i][2] for i in range(4)]
        buttons=[]
        for sh in qs.shapes:
            if sh.shape_type == 1 and getattr(sh,'has_text_frame',False) and sh.width > Inches(5): buttons.append(sh)
        # safer: use shapes containing option text
        for i,opt in enumerate(q['options']):
            found=None
            for sh in qs.shapes:
                if getattr(sh,'has_text_frame',False) and sh.text.strip()==clean_text(opt): found=sh; break
            if found: found.click_action.target_slide=targets[i]
    return start_page + len(question_slides)*5

def build_lesson_pptx(lesson,config):
    prs=Presentation(); prs.slide_width,prs.slide_height=Inches(13.333),Inches(7.5); theme=THEMES[config.theme_name]; blank=prs.slide_layouts[6]
    add_cover(prs,lesson.get('title') or config.lesson,config,theme); page=2
    for sd in lesson['slides']:
        s=prs.slides.add_slide(blank); add_full_background(s,(255,255,255)); add_header(s,sd['title'],theme,page,sd.get('activity','BÀI GIẢNG'))
        bullets=sd.get('bullets',[]); text='\n'.join('• '+clean_text(x) for x in bullets)
        add_text(s,text,.8,1.65,7.0,4.7,21)
        if sd.get('graph'):
            try: s.shapes.add_picture(create_graph(sd['graph']),Inches(8.15),Inches(1.55),width=Inches(4.6))
            except Exception: pass
        if config.include_answers and sd.get('answer'): add_text(s,'ĐÁP ÁN/GỢI Ý: '+sd['answer'],.8,6.35,11.6,.45,14,theme['primary'],True)
        if config.include_notes and sd.get('teacher_note'):
            try: s.notes_slide.notes_text_frame.text=sd['teacher_note']
            except Exception: pass
        page+=1
    return prs

def build_exam_pptx(exam,config):
    prs=Presentation(); prs.slide_width,prs.slide_height=Inches(13.333),Inches(7.5); theme=THEMES[config.theme_name]
    add_cover(prs,exam.get('title') or ('ĐỀ ÔN TẬP '+config.lesson),config,theme)
    add_exam_interactive(prs,exam,config,theme,2)
    # final QA slide
    s=prs.slides.add_slide(prs.slide_layouts[6]); add_full_background(s,(255,255,255)); add_header(s,'BÁO CÁO KIỂM CHỨNG',theme,len(prs.slides),'MATH ENGINE')
    qa=exam.get('qa_summary',{}); add_text(s,f"PASS: {qa.get('pass',0)}    FAIL: {qa.get('fail',0)}    CẦN DUYỆT: {qa.get('manual',0)}",.8,1.7,11.5,.8,26,theme['primary'],True)
    add_text(s,'Các câu FAIL phải sửa trước khi sử dụng. Các câu CẦN DUYỆT vẫn cần giáo viên kiểm tra vì chưa có bộ giải tự động phù hợp.',.8,2.8,11.5,1.5,19)
    return prs

# ---------------- UI ----------------
st.set_page_config(page_title='Trợ lý PowerPoint Toán THPT V3.1',page_icon='📐',layout='wide')
st.markdown('<style>.block-container{padding-top:1.2rem;max-width:1280px}.stButton>button{font-weight:700;border-radius:10px}</style>',unsafe_allow_html=True)
st.title('📐 Trợ lý PowerPoint Toán THPT — V3.1')
st.caption(APP_VERSION+' • AI tạo đề • Math Engine tự kiểm chứng • PowerPoint tương tác')

api_key=st.secrets.get('GEMINI_API_KEY','') if hasattr(st,'secrets') else ''
if not api_key: st.error('Chưa cấu hình GEMINI_API_KEY trong Secrets.'); st.stop()
genai.configure(api_key=api_key)
with st.sidebar:
    st.header('1. Hồ sơ')
    teacher=st.text_input('Tên giáo viên',placeholder='Hồ Thuyết Dũng'); school=st.text_input('Trường')
    grade=st.selectbox('Khối lớp',['Toán 10','Toán 11','Toán 12']); book=st.selectbox('Bộ sách',['Kết nối tri thức','Cánh Diều','Chân trời sáng tạo','Tài liệu riêng'])
    lesson=st.text_input('Bài/chuyên đề',placeholder='Tính đơn điệu và cực trị của hàm số'); periods=st.number_input('Số tiết',1,8,2)
    student_level=st.selectbox('Đối tượng',['Còn hạn chế','Trung bình – khá','Đồng đều','Khá – giỏi'])
    theme_name=st.selectbox('Phong cách',list(THEMES))
    st.header('2. Chế độ')
    mode=st.radio('Sản phẩm',['Bài giảng PowerPoint','Tạo đề + PowerPoint tương tác'])
    teaching_mode=st.selectbox('Mục đích',['Dạy kiến thức mới','Luyện tập chuyên đề','Chữa đề','Ôn thi TN.THPT','Tổng ôn'])
    exam_mode=st.selectbox('Mức độ',['Nhận biết – Thông hiểu','Nhận biết – Thông hiểu – Vận dụng','Đầy đủ 4 mức độ'])
    source_priority=st.selectbox('Ưu tiên nguồn',['Chỉ dùng tài liệu nguồn','Ưu tiên nguồn + kiến thức chuẩn','AI hỗ trợ mở rộng'])
    question_count=st.slider('Số câu đề',5,30,15); question_types=st.text_input('Dạng câu',value='Trắc nghiệm 4 lựa chọn; tính giá trị; đạo hàm; phương trình')
    include_answers=st.checkbox('Đưa đáp án/gợi ý',True); include_notes=st.checkbox('Ghi chú giáo viên',True); interaction=st.checkbox('PowerPoint tương tác',True)
    st.header('3. AI')
    try: models=[m.name for m in genai.list_models() if 'generateContent' in getattr(m,'supported_generation_methods',[])]
    except Exception: models=[]
    selected_model=st.selectbox('Mô hình AI',models,index=0) if models else 'models/gemini-1.5-flash'

st.subheader('4. Tài liệu nguồn')
uploaded=st.file_uploader('PDF, Word hoặc TXT (tối đa 20 MB)',type=['pdf','docx','txt'])
if mode.startswith('Tạo đề'):
    st.info('Luồng: Tài liệu → AI tạo câu hỏi có metadata kiểm chứng → Math Engine giải độc lập → loại/cảnh báo câu sai → PowerPoint có nút A/B/C/D và phản hồi tức thời.')
else:
    st.info('Luồng: Tài liệu → AI cấu trúc bài giảng → kiểm tra đồ thị → PowerPoint 16:9.')

if st.button('🚀 CHẠY V3.1',type='primary',use_container_width=True,disabled=uploaded is None):
    config=LessonConfig(teacher,school,grade,book,lesson,int(periods),student_level,30,theme_name,include_answers,include_notes,teaching_mode,exam_mode,interaction,source_priority,int(question_count),question_types)
    try:
        with st.status('Đang xử lý…',expanded=True) as status:
            source_text,source_bytes,source_type=read_source(uploaded); st.write('① Đọc tài liệu nguồn')
            prompt=build_prompt(config,source_text,exam=mode.startswith('Tạo đề')); st.write('② AI tạo dữ liệu có thể kiểm chứng')
            data=generate_json(selected_model,source_text,source_bytes,source_type,prompt)
            if mode.startswith('Tạo đề'):
                exam=normalize_exam(data,question_count); st.write('③ Math Engine giải/kiểm chứng độc lập')
                exam,rows=verify_exam(exam); st.write(f"PASS {exam['qa_summary']['pass']} • FAIL {exam['qa_summary']['fail']} • Cần duyệt {exam['qa_summary']['manual']}")
                if exam['qa_summary']['fail']>0: st.warning('Có câu FAIL. Các câu FAIL vẫn được giữ trong báo cáo nhưng KHÔNG nên sử dụng cho học sinh.')
                prs=build_exam_pptx(exam,config)
            else:
                st.write('③ Kiểm tra dữ liệu toán/đồ họa'); prs=build_lesson_pptx(data,config); exam=None; rows=[]
            st.write('④ Dựng PowerPoint 16:9 + tương tác'); out=io.BytesIO(); prs.save(out); pptx_bytes=out.getvalue(); status.update(label='Hoàn tất V3.1',state='complete',expanded=False)
        st.success(f'Đã tạo PowerPoint ({len(prs.slides)} slide).')
        if rows:
            with st.expander('🔎 Bảng kiểm chứng Math Engine',expanded=True): st.dataframe(rows,use_container_width=True)
        filename=('De_Toan_TuongTac' if exam else 'Bai_giang_Toan')+'_V3_1_'+uuid.uuid4().hex[:6]+'.pptx'
        st.download_button('📥 Tải PowerPoint V3.1',pptx_bytes,filename,'application/vnd.openxmlformats-officedocument.presentationml.presentation',use_container_width=True)
        if exam: st.download_button('📄 Tải JSON đề + kết quả kiểm chứng',json.dumps(exam,ensure_ascii=False,indent=2), 'exam_verified.json','application/json',use_container_width=True)
    except Exception as exc:
        st.error(f'Không thể tạo sản phẩm: {exc}')

with st.expander('🧪 Math Engine — kiểm tra nhanh'):
    expr=st.text_input('Biểu thức hàm số',value='x**3-3*x')
    if st.button('Phân tích hàm số'): 
        if sp is None: st.error('Thiếu SymPy')
        else:
            x=sp.Symbol('x'); f=normalize_sympy(expr); st.json({'expression':expr,'derivative':str(sp.diff(f,x)) if f is not None else None})

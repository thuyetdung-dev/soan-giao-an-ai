"""MathViz V9: parse, validate, render and import structured math visuals."""
from __future__ import annotations

import html
import io
import json
import re
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


MATHVIZ_RE = re.compile(r"<div\s+data-mathviz=(['\"])(.*?)\1\s*>\s*</div>", re.I | re.S)
SUPPORTED = {"dothi", "bbt", "xetdau", "net"}


def display_math_text(value: Any) -> str:
    """Convert common inline LaTeX to classroom-readable Unicode for text boxes."""
    text=str(value or "").replace("<br>", " · ").replace("<br/>", " · ").replace("$", "")
    for _ in range(3):
        text=re.sub(r"\\(?:d?frac)\{([^{}]+)\}\{([^{}]+)\}",r"(\1)/(\2)",text)
        text=re.sub(r"\\sqrt\{([^{}]+)\}",r"√(\1)",text)
        text=re.sub(r"\\text\{([^{}]+)\}",r"\1",text)
    replacements={r"\mathbb{R}":"ℝ",r"\infty":"∞",r"\perp":"⟂",r"\Rightarrow":"⇒",r"\Leftrightarrow":"⇔",
                  r"\times":"×",r"\cup":"∪",r"\neq":"≠",r"\geq":"≥",r"\ge":"≥",r"\leq":"≤",r"\le":"≤",
                  r"\varphi":"φ",r"\phi":"φ",r"\forall":"∀",r"\setminus":"∖",r"\prime":"′"}
    for old,new in replacements.items(): text=text.replace(old,new)
    text=re.sub(r"\\([A-Za-z]+)",r"\1",text); text=text.replace("{","").replace("}","")
    return re.sub(r"\s+"," ",text).strip()


def extract_mathviz(text: str) -> tuple[str, list[dict[str, Any]], list[str]]:
    visuals: list[dict[str, Any]] = []
    errors: list[str] = []
    def replace(match: re.Match) -> str:
        raw = html.unescape(match.group(2))
        try:
            payload = json.loads(raw)
            ok, detail = validate_visual(payload)
            if not ok:
                errors.append(detail)
            else:
                visuals.append({"type": payload["type"], "placement": "below_question", "payload": payload,
                                "teacher_approved": True, "source": "data-mathviz"})
        except Exception as exc:
            errors.append(f"Không đọc được data-mathviz: {exc}")
        return ""
    cleaned = MATHVIZ_RE.sub(replace, str(text or ""))
    return re.sub(r"\s+", " ", cleaned).strip(), visuals, errors


def validate_visual(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict): return False, "Visual phải là một object JSON."
    kind = str(payload.get("type", "")).strip()
    if kind not in SUPPORTED: return False, f"Kiểu visual '{kind}' chưa được hỗ trợ."
    if kind == "dothi":
        if not payload.get("fn") and not payload.get("pieces"): return False, "Đồ thị thiếu fn hoặc pieces."
        try:
            if float(payload.get("xmax", 5)) <= float(payload.get("xmin", -5)): return False, "Đồ thị có miền x không hợp lệ."
            if float(payload.get("ymax", 5)) <= float(payload.get("ymin", -5)): return False, "Đồ thị có miền y không hợp lệ."
        except Exception: return False, "Giới hạn trục của đồ thị phải là số."
    elif kind == "bbt":
        nodes, marks, signs, vals = (payload.get(k, []) for k in ("nodes", "marks", "signs", "vals"))
        if len(nodes) < 2 or len(signs) != len(nodes)-1 or len(marks) != len(nodes) or len(vals) != len(nodes):
            return False, "BBT sai số lượng nodes/marks/signs/vals."
    elif kind == "xetdau":
        nodes, rows = payload.get("nodes", []), payload.get("rows", [])
        if len(nodes) < 2 or not rows: return False, "Bảng xét dấu thiếu nodes hoặc rows."
        for row in rows:
            if len(row.get("signs", [])) != len(nodes)-1 or len(row.get("marks", [])) != len(nodes):
                return False, "Một dòng bảng xét dấu sai số lượng signs/marks."
    elif kind == "net":
        try:
            if float(payload.get("width", 0)) <= 0 or float(payload.get("height", 0)) <= 0: return False, "Hình triển khai thiếu kích thước."
        except Exception: return False, "Kích thước hình triển khai phải là số."
    return True, "Visual hợp lệ."


def _finish(fig) -> io.BytesIO:
    out = io.BytesIO(); fig.savefig(out, format="png", dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig); out.seek(0); return out


def _render_table(payload: dict, sign_table: bool = False) -> io.BytesIO:
    nodes = payload["nodes"]
    rows = payload.get("rows", []) if sign_table else [
        {"label": payload.get("dlabel", "f′(x)"), "signs": payload["signs"], "marks": payload["marks"]},
        {"label": payload.get("flabel", "f(x)"), "vals": payload["vals"]},
    ]
    ncols = 2*len(nodes)-1; nrows = 1+len(rows)
    fig, ax = plt.subplots(figsize=(max(8, ncols*.75), max(2.5, nrows*.82))); ax.axis("off")
    cells = [[""]*(ncols+1) for _ in range(nrows)]
    cells[0][0] = "x"
    for i,node in enumerate(nodes): cells[0][1+2*i] = str(node).replace("oo", "∞")
    for r,row in enumerate(rows,1):
        cells[r][0] = str(row.get("label", ""))
        if sign_table:
            for i,mark in enumerate(row.get("marks", [])): cells[r][1+2*i] = str(mark)
            for i,sign in enumerate(row.get("signs", [])): cells[r][2+2*i] = str(sign)
        elif "signs" in row:
            for i,mark in enumerate(row.get("marks", [])): cells[r][1+2*i] = str(mark)
            for i,sign in enumerate(row.get("signs", [])): cells[r][2+2*i] = str(sign)
        else:
            vals=row.get("vals", [])
            for i,val in enumerate(vals):
                if isinstance(val,dict):
                    text = str(val.get("t", "")) or f"{val.get('l','')} | {val.get('r','')}"
                else: text=str(val)
                cells[r][1+2*i]=text.replace("oo","∞")
            signs=payload.get("signs", [])
            for i,s in enumerate(signs): cells[r][2+2*i] = "↗" if s=="+" else "↘" if s=="-" else "→"
    table=ax.table(cellText=cells,loc="center",cellLoc="center")
    table.auto_set_font_size(False); table.set_fontsize(13); table.scale(1,1.75)
    for (r,c),cell in table.get_celld().items():
        cell.set_edgecolor("#24445c"); cell.set_linewidth(1.1)
        if c==0 or r==0: cell.set_facecolor("#eaf6f8"); cell.get_text().set_weight("bold")
        elif r==nrows-1 and c%2==0: cell.get_text().set_color("#087f8c"); cell.get_text().set_fontsize(18)
    return _finish(fig)


def _render_net(payload: dict) -> io.BytesIO:
    width=float(payload.get("width",16)); height=float(payload.get("height",10)); cut=payload.get("cut","x")
    x = min(width,height)*.15 if not isinstance(cut,(int,float)) else float(cut)
    fig,ax=plt.subplots(figsize=(8,5)); ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(plt.Rectangle((0,0),width,height,fill=False,lw=2,color="#17324d"))
    for xx in (x,width-x): ax.plot([xx,xx],[0,height],color="#087f8c",lw=1.6,ls="--")
    for yy in (x,height-x): ax.plot([0,width],[yy,yy],color="#087f8c",lw=1.6,ls="--")
    for px,py in ((0,0),(width-x,0),(0,height-x),(width-x,height-x)):
        ax.add_patch(plt.Rectangle((px,py),x,x,facecolor="#f7d9a7",edgecolor="#b26a00",lw=1.5,alpha=.65))
    for px,py in ((x/2,x/2),(width-x/2,x/2),(x/2,height-x/2),(width-x/2,height-x/2)):
        ax.text(px,py,str(cut),ha="center",va="center",fontsize=14,weight="bold")
    ax.annotate(str(payload.get("width_label",int(width))),xy=(width/2,-.45),ha="center",va="top",fontsize=14)
    ax.annotate(str(payload.get("height_label",int(height))),xy=(-.45,height/2),ha="right",va="center",fontsize=14)
    ax.set_xlim(-1.4,width+1); ax.set_ylim(-1.2,height+1)
    return _finish(fig)


def render_visual(payload: dict, graph_renderer=None) -> io.BytesIO | None:
    ok,_=validate_visual(payload)
    if not ok: return None
    kind=payload["type"]
    if kind=="dothi" and graph_renderer:
        graph={"expression":payload.get("fn","x"),"x_min":payload.get("xmin",-5),"x_max":payload.get("xmax",5),
               "y_min":payload.get("ymin"),"y_max":payload.get("ymax"),"points":payload.get("points",[]),
               "xticks":payload.get("xticks",[]),"yticks":payload.get("yticks",[]),"caption":payload.get("caption","")}
        return graph_renderer(graph)
    if kind=="bbt": return _render_table(payload)
    if kind=="xetdau": return _render_table(payload,True)
    if kind=="net": return _render_net(payload)
    return None


def question_bank_to_lesson(data: dict, title: str="Bài giảng từ ngân hàng câu hỏi") -> tuple[dict,list[str]]:
    if not isinstance(data,dict) or not any(k in data for k in ("mcq","tf","sa")):
        raise ValueError("Không phải JSON ngân hàng câu hỏi mcq/tf/sa.")
    slides=[]; warnings=[]; number=0
    for kind in ("mcq","tf","sa"):
        for item in data.get(kind,[]) or []:
            number+=1; question,visuals,errors=extract_mathviz(item.get("q","")); warnings.extend(f"Câu {number}: {e}" for e in errors)
            question=display_math_text(question)
            # Phục hồi xác định được cho bài toán cắt bốn góc của tấm bìa.
            if not visuals and re.search(r"tấm\s+bìa.*cắt\s+bỏ\s+bốn\s+hình\s+vuông",question,re.I):
                dims=re.search(r"(?:kích\s+thước\s*)?(\d+(?:[.,]\d+)?)\s*(?:cm)?\s*[×x]\s*(\d+(?:[.,]\d+)?)",question,re.I)
                if dims:
                    height=float(dims.group(1).replace(",",".")); width=float(dims.group(2).replace(",","."))
                    payload={"type":"net","shape":"open_box","width":width,"height":height,"cut":"x","showCutLines":True}
                    visuals=[{"type":"net","placement":"below_question","payload":payload,"teacher_approved":True,"source":"deterministic_recovery"}]
            if kind=="mcq":
                opts=[f"{chr(65+i)}. {display_math_text(v)}" for i,v in enumerate(item.get("opts",[])[:4])]
                ans=item.get("ans",0); answer=f"Đáp án {chr(65+ans)}. {display_math_text(item.get('exp',''))}" if isinstance(ans,int) and 0<=ans<4 else display_math_text(item.get("exp",""))
            elif kind=="tf":
                opts=[f"{chr(97+i)}) {display_math_text(v.get('t',''))}" for i,v in enumerate(item.get("stmts",[])[:4])]
                truth=["Đ" if v.get("ans") else "S" for v in item.get("stmts",[])[:4]]; answer=" - ".join(truth)+". "+display_math_text(item.get("exp",""))
            else:
                opts=[]; answer=f"Đáp án: {display_math_text(item.get('ans',''))}. {display_math_text(item.get('exp',''))}"
            needs_reference=bool(re.search(r"(?:như|theo|trong)\s+hình|hình\s+(?:bên|dưới)|bảng\s+biến\s+thiên\s+(?:sau|như)|đồ\s+thị\s+(?:sau|như)|tấm\s+bìa.*cắt",question,re.I))
            if needs_reference and not visuals: warnings.append(f"Câu {number}: tham chiếu hình nhưng JSON không có data-mathviz; cần giáo viên bổ sung.")
            slides.append({"title":f"Câu {number} — {kind.upper()}","subtitle":item.get("tag",""),"activity":"LUYỆN TẬP",
                "layout":"visual" if visuals else "quiz","bullets":opts,"formulas":[],"question":question,"product":"Trình bày đáp án và lập luận.",
                "answer":answer,"teacher_note":"Mức độ: "+str(item.get("lvl","")),"source_ref":"JSON ngân hàng câu hỏi do giáo viên cung cấp",
                "visuals":visuals,"visual_requirement":{"required":needs_reference or bool(visuals),"type":visuals[0]["type"] if visuals else "source_image" if needs_reference else "","reason":"Câu hỏi tham chiếu trực quan."}})
    return {"title":title,"objectives":["Củng cố kiến thức và rèn luyện năng lực giải quyết vấn đề toán học."],"slides":slides,"_import_warnings":warnings},warnings

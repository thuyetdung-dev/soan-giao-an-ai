"""Hệ thống thẩm định đề Toán V3.3 - deterministic, offline-first."""
from __future__ import annotations
import math, re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from typing import Any
try:
    import sympy as sp
except Exception:
    sp = None

@dataclass
class AuditIssue:
    code: str
    severity: str
    message: str
    evidence: str = ""
    suggestion: str = ""
    def to_dict(self): return asdict(self)

def norm_text(v: Any) -> str:
    s = str(v or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return re.sub(r"[^0-9a-zà-ỹα-ω]+", "", s)

def normalize_math_text(v: Any) -> str:
    s = str(v or "").strip().replace("−","-").replace("–","-").replace("×","*").replace("÷","/")
    s = s.replace("^","**")
    s = re.sub(r"\\left|\\right", "", s)
    return re.sub(r"\s+", "", s)

def parse_number(v: Any):
    if isinstance(v,bool): return None
    if isinstance(v,(int,float)): return float(v)
    try: return float(str(v or "").strip().replace(",",".").replace("−","-"))
    except Exception: return None

def sympy_parse(expr: Any):
    if sp is None: raise RuntimeError("SymPy chưa được cài đặt")
    s=normalize_math_text(expr).replace("ln(","log(")
    s=re.sub(r"(?<![A-Za-z])e(?![A-Za-z])","E",s)
    x=sp.Symbol("x")
    local={"x":x,"t":sp.Symbol("t"),"pi":sp.pi,"E":sp.E,"sin":sp.sin,"cos":sp.cos,"tan":sp.tan,
           "sqrt":sp.sqrt,"log":sp.log,"exp":sp.exp,"abs":sp.Abs,"asin":sp.asin,"acos":sp.acos,"atan":sp.atan}
    return sp.sympify(s,locals=local)

def expressions_equal(a,b):
    try: return bool(sp.simplify(sympy_parse(a)-sympy_parse(b))==0)
    except Exception: return None

def finite_numeric_eval(expr, subs=None):
    try:
        e=sympy_parse(expr); sub={sp.Symbol(k):v for k,v in (subs or {}).items()}; z=sp.N(e.subs(sub))
        return float(z) if z.is_real and z.is_finite else None
    except Exception: return None

def domain_of(expr):
    try: return str(sp.calculus.util.continuous_domain(sympy_parse(expr),sp.Symbol("x"),sp.S.Reals))
    except Exception as e: return f"UNKNOWN: {e}"

def _idx(q):
    idx=q.get("answer_index",q.get("answer"))
    if isinstance(idx,str) and idx.strip().upper() in "ABCD": return "ABCD".index(idx.strip().upper())
    try: return int(idx)
    except Exception: return None

def audit_structure(q):
    issues=[]
    if not isinstance(q,dict): return [AuditIssue("Q_TYPE","FAIL","Câu hỏi không phải object JSON.")]
    if not str(q.get("question","")).strip(): issues.append(AuditIssue("Q_TEXT_EMPTY","FAIL","Thiếu nội dung câu hỏi."))
    typ=str(q.get("type","multiple_choice")).lower().strip()
    if typ in {"multiple_choice","mcq","trac_nghiem","choice"}:
        opts=q.get("options")
        if not isinstance(opts,list) or len(opts)!=4: issues.append(AuditIssue("MCQ_OPTIONS_COUNT","FAIL","Câu nhiều lựa chọn phải có đúng 4 phương án."))
        else:
            d=[norm_text(x) for x in opts]; dup=[x for x,c in Counter(d).items() if x and c>1]
            if dup: issues.append(AuditIssue("MCQ_DUP_OPTIONS","FAIL","Có phương án trùng nhau.",str(dup),"Thay phương án trùng bằng nhiễu hợp lý."))
        idx=_idx(q)
        if idx not in range(4): issues.append(AuditIssue("MCQ_ANSWER_INDEX","FAIL","answer_index phải là 0,1,2 hoặc 3."))
    elif typ in {"true_false","dung_sai","truefalse"}:
        st=q.get("statements",q.get("options")); ans=q.get("answers",q.get("correct_answers"))
        if not isinstance(st,list) or not st: issues.append(AuditIssue("TF_STATEMENTS","FAIL","Câu Đúng/Sai phải có danh sách statements."))
        if not isinstance(ans,list) or len(ans)!=(len(st) if isinstance(st,list) else -1): issues.append(AuditIssue("TF_ANSWERS","FAIL","Danh sách answers không khớp số mệnh đề."))
    elif typ in {"short_answer","short","tra_loi_ngan"}:
        if q.get("expected_answer",q.get("answer")) in (None,""): issues.append(AuditIssue("SHORT_EXPECTED","FAIL","Câu trả lời ngắn thiếu expected_answer."))
    else:
        issues.append(AuditIssue("Q_UNKNOWN_TYPE","MANUAL_REVIEW",f"Dạng câu '{typ}' chưa có bộ kiểm chứng chuyên biệt."))
    return issues

def audit_answer_uniqueness(q):
    typ=str(q.get("type","multiple_choice")).lower()
    if typ not in {"multiple_choice","mcq","trac_nghiem","choice"}: return []
    opts=q.get("options"); exp=q.get("expected_answer")
    if not isinstance(opts,list) or len(opts)!=4 or exp in (None,""): return []
    matches=[]
    for i,o in enumerate(opts):
        eq=expressions_equal(o,exp)
        if eq is True or (eq is None and parse_number(o) is not None and parse_number(exp) is not None and math.isclose(parse_number(o),parse_number(exp),rel_tol=1e-9,abs_tol=1e-9)): matches.append(i)
    if len(matches)==1:
        out=[AuditIssue("ONE_CORRECT","PASS","Xác định được đúng 1 phương án khớp đáp án chuẩn.",str(matches[0]))]
        if _idx(q)!=matches[0]: out.append(AuditIssue("ANSWER_INDEX_MISMATCH","FAIL","answer_index không trỏ tới phương án đúng đã kiểm chứng.",f"selected={_idx(q)}; expected={matches[0]}"))
        return out
    if len(matches)>1: return [AuditIssue("MULTIPLE_CORRECT","FAIL","Có từ 2 phương án trở lên khớp đáp án chuẩn.",str(matches))]
    return [AuditIssue("NO_CORRECT","FAIL","Không có phương án nào khớp đáp án chuẩn.",str(exp))]

def verify_math(q):
    check=q.get("check")
    if not isinstance(check,dict): return [AuditIssue("MATH_NO_CHECK","MANUAL_REVIEW","Câu chưa có quy tắc kiểm chứng độc lập; cần giáo viên duyệt.",suggestion="Bổ sung check.type và dữ kiện kiểm chứng.")]
    kind=str(check.get("type","")).lower().strip(); exp=q.get("expected_answer")
    try:
        if kind=="numeric_eval":
            val=finite_numeric_eval(check.get("expression"),{"x":parse_number(check.get("x"))}); e=parse_number(exp)
            if val is None or e is None: raise ValueError("Thiếu/không tính được expression, x hoặc expected_answer")
            ok=math.isclose(val,e,rel_tol=1e-8,abs_tol=1e-9)
            return [AuditIssue("NUMERIC_VERIFY","PASS" if ok else "FAIL","Tính lại giá trị số thành công." if ok else "Giá trị đáp án không khớp tính toán.",f"computed={val}; expected={e}")]
        if kind=="derivative":
            actual=sp.diff(sympy_parse(check.get("expression")),sp.Symbol("x")); eq=expressions_equal(str(actual),exp)
            return [AuditIssue("DERIVATIVE_VERIFY","PASS" if eq is True else "FAIL" if eq is False else "MANUAL_REVIEW","Đạo hàm khớp." if eq is True else "Đạo hàm không khớp." if eq is False else "Chưa xác nhận được tương đương.",f"computed={actual}; expected={exp}")]
        if kind=="derivative_value":
            x=parse_number(check.get("x")); e=parse_number(exp)
            if x is None or e is None: raise ValueError("Thiếu x/expected_answer")
            val=float(sp.N(sp.diff(sympy_parse(check.get("expression")),sp.Symbol("x")).subs(sp.Symbol("x"),x))); ok=math.isclose(val,e,rel_tol=1e-8,abs_tol=1e-9)
            return [AuditIssue("DERIVATIVE_VALUE_VERIFY","PASS" if ok else "FAIL","Giá trị đạo hàm khớp." if ok else "Giá trị đạo hàm không khớp.",f"computed={val}; expected={e}")]
        if kind=="equation":
            sol=sp.solve(sp.Eq(sympy_parse(check.get("lhs")),sympy_parse(check.get("rhs"))),sp.Symbol("x"))
            if len(sol)==1: eq=expressions_equal(str(sol[0]),exp)
            else: eq=normalize_math_text("{"+",".join(map(str,sol))+"}")==normalize_math_text(exp)
            return [AuditIssue("EQUATION_VERIFY","PASS" if eq is True else "FAIL" if eq is False else "MANUAL_REVIEW","Nghiệm phương trình khớp." if eq is True else "Nghiệm phương trình không khớp." if eq is False else "Cần kiểm tra tập nghiệm.",f"computed={sol}; expected={exp}")]
        if kind=="mcq_index":
            ok=int(check.get("correct_index"))==_idx(q); return [AuditIssue("MCQ_INDEX_VERIFY","PASS" if ok else "FAIL","Chỉ số đáp án khớp." if ok else "Chỉ số đáp án không khớp.")]
        if kind=="true_false":
            expected=q.get("answers",q.get("correct_answers")); actual=check.get("answers")
            if not isinstance(expected,list) or not isinstance(actual,list): raise ValueError("Thiếu answers")
            ok=[bool(x)==bool(y) for x,y in zip(expected,actual)] and len(expected)==len(actual)
            return [AuditIssue("TF_VERIFY","PASS" if ok else "FAIL","Đáp án Đúng/Sai khớp cấu hình kiểm chứng." if ok else "Đáp án Đúng/Sai không khớp.")]
        return [AuditIssue("MATH_UNKNOWN_CHECK","MANUAL_REVIEW",f"Loại kiểm chứng '{kind}' chưa được hỗ trợ.")]
    except Exception as e:
        return [AuditIssue("MATH_EXCEPTION","MANUAL_REVIEW","Không thể tự động kiểm chứng câu hỏi.",str(e),"Bổ sung check hoặc duyệt thủ công.")]

def audit_solution(q):
    sol=q.get("solution",q.get("explanation",q.get("teacher_solution")))
    exp=q.get("expected_answer")
    if sol in (None,""): return []
    if exp in (None,""): return [AuditIssue("SOLUTION_NO_EXPECTED","MANUAL_REVIEW","Có lời giải nhưng chưa có expected_answer để đối chiếu.")]
    ns=norm_text(sol); ne=norm_text(exp)
    if ne and ne in ns: return [AuditIssue("SOLUTION_CONSISTENCY","PASS","Lời giải có chứa kết quả mong đợi.")]
    return [AuditIssue("SOLUTION_CONSISTENCY","MANUAL_REVIEW","Chưa chứng minh được lời giải phù hợp với expected_answer.",f"expected={exp}","Giáo viên kiểm tra bước giải và kết luận.")]

def audit_domain(q):
    expr=(q.get("check") or {}).get("expression") if isinstance(q.get("check"),dict) else None
    expr=expr or q.get("expression")
    if not expr: return []
    d=domain_of(expr)
    return [AuditIssue("DOMAIN_CHECK","PASS","Đã xác định miền xác định bằng SymPy.",d)] if not d.startswith("UNKNOWN:") else [AuditIssue("DOMAIN_UNKNOWN","MANUAL_REVIEW","Chưa xác định được miền xác định.",d)]

def audit_question(q):
    issues=audit_structure(q)+audit_domain(q)+verify_math(q)+audit_answer_uniqueness(q)+audit_solution(q)
    sev={i.severity for i in issues}; status="FAIL" if "FAIL" in sev else "MANUAL_REVIEW" if "MANUAL_REVIEW" in sev else "PASS"
    return {"status":status,"issues":[i.to_dict() for i in issues]}

def audit_blueprint(exam):
    issues=[]; bp=exam.get("blueprint")
    qs=exam.get("questions",[])
    if not isinstance(bp,dict): return issues
    try:
        if bp.get("total_questions") is not None and int(bp["total_questions"])!=len(qs): issues.append(AuditIssue("BLUEPRINT_TOTAL","FAIL","Số câu không khớp ma trận.",f"expected={bp['total_questions']}; actual={len(qs)}"))
    except Exception: issues.append(AuditIssue("BLUEPRINT_TOTAL_FORMAT","FAIL","total_questions trong ma trận không hợp lệ."))
    for field, getter in [("type_distribution",lambda q:str(q.get("type","multiple_choice")).lower()),("level_distribution",lambda q:str(q.get("level","")).lower()),("topic_distribution",lambda q:str(q.get("topic","")).strip())]:
        for key,expected in (bp.get(field) or {}).items():
            if field == "topic_distribution":
                actual=sum(1 for q in qs if getter(q)==str(key).strip())
            else:
                actual=sum(1 for q in qs if getter(q)==str(key).lower())
            if int(expected)!=actual: issues.append(AuditIssue("BLUEPRINT_"+field.upper(),"FAIL",f"Phân bố '{key}' không khớp.",f"expected={expected}; actual={actual}"))
    return issues

def normalize_exam(data):
    out=dict(data); qs=[]
    for i,q0 in enumerate(data.get("questions",[]),1):
        q=dict(q0); q.setdefault("id",f"Q{i}"); q.setdefault("type","multiple_choice")
        if "answer_index" not in q and "answer" in q: q["answer_index"]=q["answer"]
        if isinstance(q.get("answer_index"),str) and q["answer_index"].strip().upper() in "ABCD": q["answer_index"]="ABCD".index(q["answer_index"].strip().upper())
        qs.append(q)
    out["questions"]=qs; return out

def audit_exam(exam):
    if not isinstance(exam,dict): return {"status":"FAIL","summary":{},"questions":[],"exam_issues":[AuditIssue("EXAM_TYPE","FAIL","Đề không phải JSON object.").to_dict()]}
    qs=exam.get("questions")
    if not isinstance(qs,list) or not qs: return {"status":"FAIL","summary":{},"questions":[],"exam_issues":[AuditIssue("EXAM_QUESTIONS","FAIL","Không có danh sách câu hỏi.").to_dict()]}
    exam_issues=audit_blueprint(exam)
    texts=defaultdict(list)
    for i,q in enumerate(qs,1): texts[norm_text(q.get("question"))].append(i)
    for g in [v for k,v in texts.items() if k and len(v)>1]: exam_issues.append(AuditIssue("DUPLICATE_QUESTIONS","FAIL","Phát hiện câu hỏi trùng nội dung.",str(g)))
    for a in range(len(qs)):
        for b in range(a+1,len(qs)):
            x=norm_text(qs[a].get("question")); y=norm_text(qs[b].get("question"))
            if x and y and x!=y:
                sim=SequenceMatcher(None,x,y).ratio()
                if sim>=0.90: exam_issues.append(AuditIssue("NEAR_DUPLICATE","MANUAL_REVIEW","Hai câu có nội dung gần trùng.",f"Q{a+1} ↔ Q{b+1}; similarity={sim:.2f}"))
    rows=[]
    for i,q in enumerate(qs,1): rows.append({"number":i,"id":q.get("id",f"Q{i}"),"topic":q.get("topic",""),"level":q.get("level",""),"type":q.get("type",""),"question":q.get("question",""),**audit_question(q)})
    counts=Counter(r["status"] for r in rows); total=len(rows); fail=counts["FAIL"]; manual=counts["MANUAL_REVIEW"]; passed=counts["PASS"]
    overall="FAIL" if fail or any(i.severity=="FAIL" for i in exam_issues) else "MANUAL_REVIEW" if manual or any(i.severity=="MANUAL_REVIEW" for i in exam_issues) else "PASS"
    score=round(max(0,100-100*fail/total-30*manual/total-5*sum(i.severity=="FAIL" for i in exam_issues)-2*sum(i.severity=="MANUAL_REVIEW" for i in exam_issues)),1)
    return {"status":overall,"summary":{"total":total,"pass":passed,"fail":fail,"manual_review":manual,"score":score,"exam_issues":len(exam_issues)},"exam_issues":[i.to_dict() for i in exam_issues],"questions":rows}

def auto_fix_exam(exam):
    """Chỉ sửa lỗi kỹ thuật xác định chắc chắn; tuyệt đối không đoán/sửa nội dung toán."""
    fixed=normalize_exam(exam); changes=[]
    for i,q in enumerate(fixed.get("questions",[]),1):
        # Chuẩn hóa answer_index từ A/B/C/D.
        raw=q.get("answer_index")
        if isinstance(raw,str) and raw.strip().upper() in "ABCD":
            new="ABCD".index(raw.strip().upper())
            if q.get("answer_index") != new:
                q["answer_index"]=new; changes.append(f"Q{i}: answer_index A/B/C/D → {new}")
        elif "answer_index" not in q and isinstance(q.get("answer"),str) and q["answer"].strip().upper() in "ABCD":
            q["answer_index"]="ABCD".index(q["answer"].strip().upper()); changes.append(f"Q{i}: answer → answer_index={q['answer_index']}")
        # Đồng bộ chỉ số khi expected_answer khớp duy nhất một phương án.
        opts=q.get("options"); exp=q.get("expected_answer")
        if isinstance(opts,list) and len(opts)==4 and exp not in (None,""):
            matches=[]
            for k,o in enumerate(opts):
                eq=expressions_equal(o,exp)
                if eq is True: matches.append(k)
                elif eq is None:
                    a,b=parse_number(o),parse_number(exp)
                    if a is not None and b is not None and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9): matches.append(k)
            if len(matches)==1 and _idx(q)!=matches[0]:
                q["answer_index"]=matches[0]; changes.append(f"Q{i}: đồng bộ answer_index={matches[0]} theo expected_answer")
    return fixed,changes

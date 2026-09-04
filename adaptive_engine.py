"""V4.5 Adaptive Exam Intelligence: multi-form generation, difficulty heuristics, variant QA."""
import json, re, hashlib
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, timezone

LEVEL_WEIGHT = {"nhận biết":1, "thông hiểu":2, "vận dụng":3, "vận dụng cao":4}

def norm(s): return re.sub(r"\s+", " ", str(s or "")).strip().lower()

def question_type(q):
    t=norm(q.get("type","mcq"))
    if t in {"mcq","multiple_choice","trac_nghiem","trắc nghiệm"}: return "mcq"
    if t in {"true_false","tf","dung_sai","đúng_sai"}: return "true_false"
    if t in {"short_answer","short","tra_loi_ngan","trả lời ngắn"}: return "short_answer"
    return t

def difficulty_score(q):
    """Heuristic 0-100. It is a screening signal, not psychometric calibration."""
    text=norm(q.get("question")); level=LEVEL_WEIGHT.get(norm(q.get("level")),1)
    score=18+level*14
    score += min(22, max(0, len(text)-80)/25)
    signals=["tham số","biện luận","tối ưu","chứng minh","tất cả","m\b","kết hợp","suy luận"]
    score += sum(5 for s in signals if re.search(s,text))
    if question_type(q)=="mcq": score += 3
    if question_type(q)=="true_false": score += 4
    if question_type(q)=="short_answer": score += 6
    return round(min(100,score),1)

def distractor_diagnostics(q):
    if question_type(q)!="mcq": return []
    opts=q.get("options") or []
    out=[]
    if len(opts)!=4: return out
    for i in range(4):
        for j in range(i+1,4):
            r=SequenceMatcher(None,norm(opts[i]),norm(opts[j])).ratio()
            if r>=.92: out.append({"code":"NEAR_DUPLICATE","severity":"REVIEW","pair":f"{i+1}-{j+1}","score":round(r,2)})
    lens=[len(norm(x)) for x in opts]
    if max(lens)-min(lens)>=90: out.append({"code":"LENGTH_BIAS","severity":"REVIEW","evidence":lens})
    ans=q.get("answer_index")
    if isinstance(ans,int) and 0<=ans<4:
        other=[len(norm(opts[i])) for i in range(4) if i!=ans]
        if other and len(norm(opts[ans]))>max(other)*1.8: out.append({"code":"ANSWER_LENGTH_BIAS","severity":"REVIEW"})
    return out

def analyze_exam(exam):
    qs=exam.get("questions",[]) if isinstance(exam,dict) else []
    rows=[]
    for i,q in enumerate(qs,1):
        rows.append({"number":i,"id":q.get("id",f"Q{i}"),"level":q.get("level",""),"topic":q.get("topic",""),"type":question_type(q),"difficulty":difficulty_score(q),"distractors":distractor_diagnostics(q)})
    vals=[r["difficulty"] for r in rows]
    avg=round(sum(vals)/len(vals),1) if vals else 0
    spread=round(max(vals)-min(vals),1) if vals else 0
    return {"summary":{"total":len(rows),"avg_difficulty":avg,"spread":spread},"questions":rows}

def variant_blueprint(base, code_count):
    return {"base":base,"variant_count":code_count,"rule":"Giữ nguyên ma trận, số câu, loại câu và mức độ; chỉ thay đổi thứ tự câu/phương án hoặc tham số khi AI cung cấp biến thể đã kiểm chứng."}

def variant_consistency(variants):
    if not variants: return {"status":"REVIEW","issues":["Chưa có mã đề"]}
    base=variants[0]; issues=[]
    n=len(base.get("questions",[]))
    for idx,v in enumerate(variants[1:],2):
        if len(v.get("questions",[]))!=n: issues.append(f"Mã {idx}: khác số câu")
        levels=Counter(norm(q.get("level")) for q in v.get("questions",[]))
        base_levels=Counter(norm(q.get("level")) for q in base.get("questions",[]))
        if levels!=base_levels: issues.append(f"Mã {idx}: lệch phân bố mức độ")
        types=Counter(question_type(q) for q in v.get("questions",[])); base_types=Counter(question_type(q) for q in base.get("questions",[]))
        if types!=base_types: issues.append(f"Mã {idx}: lệch phân bố loại câu")
    return {"status":"FAIL" if issues else "PASS","issues":issues}

def fingerprint(exam):
    payload=json.dumps(exam,ensure_ascii=False,sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest().upper()

def build_manifest(variants, base_report=None):
    return {"version":"4.5.0","created_at":datetime.now(timezone.utc).isoformat(),"variant_count":len(variants),"fingerprints":[fingerprint(v) for v in variants],"consistency":variant_consistency(variants),"base_report":base_report or {}}

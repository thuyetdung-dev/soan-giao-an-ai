"""V5.0 orchestration: Question DNA, bank selection, multi-code, coverage and release gate."""
import copy, random, hashlib, json
from collections import Counter
from question_bank import fingerprint, qtype, norm
from adaptive_engine import analyze_exam, variant_consistency

def coverage_report(exam):
    qs=exam.get("questions",[]); total=len(qs)
    return {"total":total,"types":dict(Counter(qtype(q) for q in qs)),"levels":dict(Counter(norm(q.get("level")) for q in qs)),"topics":dict(Counter(norm(q.get("topic")) for q in qs)),"unique":len({fingerprint(q) for q in qs})}

def build_variants(exam,n=4,seed=2026):
    variants=[]
    for i in range(max(1,int(n))):
        v=copy.deepcopy(exam); rng=random.Random(seed+i)
        rng.shuffle(v.get("questions",[]))
        for q in v.get("questions",[]):
            if qtype(q)=="mcq" and len(q.get("options",[]))==4:
                old=list(q["options"]); ans=q.get("answer_index"); order=list(range(4)); rng.shuffle(order)
                q["options"]=[old[j] for j in order]
                if isinstance(ans,int) and ans in order: q["answer_index"]=order.index(ans)
        v["variant_code"]=chr(65+i) if i<26 else f"V{i+1}"
        v["fingerprint"]=hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest().upper()
        variants.append(v)
    return variants

def release_gate(math_report,ped_report,council=None,variant_report=None):
    council=council or []; variant_report=variant_report or {"status":"PASS"}
    statuses=[math_report.get("status"),ped_report.get("status")]+[c.get("status") for c in council]
    if "FAIL" in statuses or variant_report.get("status")=="FAIL": return "REJECTED"
    if any(s in {"MANUAL_REVIEW","REVIEW"} for s in statuses): return "CONDITIONAL"
    return "CERTIFIED"

def manifest(exam,variants,gate):
    return {"version":"5.0.0","release_gate":gate,"base_fingerprint":fingerprint(exam),"variants":[{"code":v.get("variant_code"),"fingerprint":v.get("fingerprint")} for v in variants],"coverage":[coverage_report(v) for v in variants],"adaptive":analyze_exam(exam),"variant_consistency":variant_consistency(variants)}

"""V5.0 Question DNA Bank: local SQLite question bank, fingerprinting, search, dedupe and analytics."""
import hashlib, json, re, sqlite3
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

LEVELS={"nhận biết":1,"thông hiểu":2,"vận dụng":3,"vận dụng cao":4}

def norm(s): return re.sub(r"\s+"," ",str(s or "")).strip().lower()
def qtype(q):
    t=norm(q.get("type","mcq")); return {"multiple_choice":"mcq","trắc nghiệm":"mcq","true_false":"true_false","đúng_sai":"true_false","short":"short_answer","trả lời ngắn":"short_answer"}.get(t,t)
def fingerprint(q):
    core={"type":qtype(q),"topic":norm(q.get("topic")),"level":norm(q.get("level")),"question":norm(q.get("question")),"options":[norm(x) for x in q.get("options",[]) or []]}
    return hashlib.sha256(json.dumps(core,ensure_ascii=False,sort_keys=True).encode()).hexdigest().upper()
def question_dna(q):
    text=norm(q.get("question")); level=norm(q.get("level")); topic=norm(q.get("topic")); typ=qtype(q)
    signals=["tham số","biện luận","tối ưu","cực trị","đồ thị","đạo hàm","logarit","mũ","xác suất","hình học","vectơ","tích phân"]
    tags=[s for s in signals if s in text]
    return {"fingerprint":fingerprint(q),"type":typ,"topic":topic,"level":level,"level_weight":LEVELS.get(level,0),"tags":tags,"text_length":len(text),"has_solution":bool(norm(q.get("solution"))),"has_check":bool(q.get("check"))}

class QuestionBank:
    def __init__(self,path="question_bank.sqlite3"):
        self.path=str(path); self.conn=sqlite3.connect(self.path); self.conn.row_factory=sqlite3.Row
        self.conn.execute("CREATE TABLE IF NOT EXISTS questions (fingerprint TEXT PRIMARY KEY, question_json TEXT NOT NULL, dna_json TEXT NOT NULL, created_at TEXT NOT NULL, uses INTEGER DEFAULT 0)")
        self.conn.commit()
    def close(self): self.conn.close()
    def add_exam(self,exam):
        added=0; dup=0
        for q in exam.get("questions",[]):
            fp=fingerprint(q); dna=question_dna(q)
            cur=self.conn.execute("SELECT 1 FROM questions WHERE fingerprint=?",(fp,))
            if cur.fetchone(): dup+=1; continue
            self.conn.execute("INSERT INTO questions VALUES (?,?,?,?,0)",(fp,json.dumps(q,ensure_ascii=False),json.dumps(dna,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
            added+=1
        self.conn.commit(); return {"added":added,"duplicates":dup}
    def search(self,topic="",level="",typ="",limit=100):
        rows=self.conn.execute("SELECT * FROM questions ORDER BY created_at DESC LIMIT ?",(limit*3,)).fetchall(); out=[]
        for r in rows:
            q=json.loads(r["question_json"]); dna=json.loads(r["dna_json"])
            if topic and norm(topic) not in norm(dna.get("topic")): continue
            if level and norm(level)!=norm(dna.get("level")): continue
            if typ and qtype(q)!=qtype({"type":typ}): continue
            q["_uses"]=r["uses"]; q["_dna"]=dna; out.append(q)
            if len(out)>=limit: break
        return out
    def count(self): return self.conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    def stats(self):
        rows=self.conn.execute("SELECT dna_json,uses FROM questions").fetchall();
        levels={}; topics={}; types={};
        for r in rows:
            d=json.loads(r[0]);
            levels[d.get("level","")]=levels.get(d.get("level",""),0)+1
            topics[d.get("topic","")]=topics.get(d.get("topic",""),0)+1
            types[d.get("type","")]=types.get(d.get("type",""),0)+1
        return {"total":len(rows),"levels":levels,"topics":topics,"types":types,"total_uses":sum(r[1] for r in rows)}
    def mark_used(self,questions):
        for q in questions: self.conn.execute("UPDATE questions SET uses=uses+1 WHERE fingerprint=?",(fingerprint(q),))
        self.conn.commit()

def select_from_bank(bank, blueprint):
    selected=[]; used=set()
    for qtype_name,count in (blueprint.get("type_distribution") or {}).items():
        for level,count_level in (blueprint.get("level_distribution") or {}).items():
            if count_level<=0: continue
            pool=bank.search(level=level,typ=qtype_name,limit=500)
            for q in pool:
                if fingerprint(q) in used: continue
                selected.append(q); used.add(fingerprint(q))
                if len([x for x in selected if norm(x.get("level"))==norm(level) and qtype(x)==qtype_name])>=min(count_level,int(count)):
                    break
    total=int(blueprint.get("total_questions",len(selected)))
    return selected[:total]

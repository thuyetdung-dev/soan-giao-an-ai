"""V3.4 deterministic math-exam audit engine."""
import re, math, json
from collections import Counter, defaultdict
from difflib import SequenceMatcher
try:
 import sympy as sp
except Exception: sp=None

def norm(s): return re.sub(r'[^0-9a-zà-ỹ]+','',str(s or '').lower())
def mexpr(s):
 s=str(s or '').strip().replace('−','-').replace('×','*').replace('÷','/').replace('^','**')
 return s.replace('ln(','log(')
def sx(s):
 if sp is None: raise RuntimeError('SymPy chưa cài')
 return sp.sympify(mexpr(s),locals={'x':sp.Symbol('x'),'pi':sp.pi,'E':sp.E,'sin':sp.sin,'cos':sp.cos,'tan':sp.tan,'sqrt':sp.sqrt,'log':sp.log,'exp':sp.exp,'abs':sp.Abs})
def equal(a,b):
 try:return bool(sp.simplify(sx(a)-sx(b))==0)
 except:return None
def num(s):
 try:return float(str(s).replace(',','.'))
 except:return None
def issue(code,severity,message,evidence='',suggestion=''): return {'code':code,'severity':severity,'message':message,'evidence':evidence,'suggestion':suggestion}

def math_check(q):
 c=q.get('check'); exp=q.get('expected_answer');
 if not isinstance(c,dict): return [issue('NO_MATH_CHECK','MANUAL_REVIEW','Chưa có quy tắc kiểm chứng độc lập.')]
 k=str(c.get('type','')).lower()
 try:
  if k=='numeric_eval':
   x=num(c.get('x')); e=num(exp); v=float(sp.N(sx(c['expression']).subs(sp.Symbol('x'),x))); ok=e is not None and math.isclose(v,e,rel_tol=1e-8,abs_tol=1e-9)
   return [issue('NUMERIC','PASS' if ok else 'FAIL','Giá trị tính lại khớp.' if ok else 'Giá trị tính lại không khớp.',f'computed={v}; expected={e}')]
  if k=='derivative':
   a=sp.diff(sx(c['expression']),sp.Symbol('x')); eq=equal(a,exp); return [issue('DERIVATIVE','PASS' if eq else 'FAIL' if eq is False else 'MANUAL_REVIEW','Đạo hàm khớp.' if eq else 'Đạo hàm không khớp.' if eq is False else 'Chưa chứng minh được tương đương.',f'computed={a}; expected={exp}')]
  if k=='derivative_value':
   x=num(c.get('x')); e=num(exp); v=float(sp.N(sp.diff(sx(c['expression']),sp.Symbol('x')).subs(sp.Symbol('x'),x))); ok=e is not None and math.isclose(v,e,rel_tol=1e-8,abs_tol=1e-9); return [issue('DERIVATIVE_VALUE','PASS' if ok else 'FAIL','Giá trị đạo hàm khớp.' if ok else 'Giá trị đạo hàm không khớp.',f'computed={v}; expected={e}')]
  if k=='equation':
   sol=sp.solve(sp.Eq(sx(c['lhs']),sx(c['rhs'])),sp.Symbol('x')); got='{'+','.join(map(str,sol))+'}'; eq=equal(str(sol[0]),exp) if len(sol)==1 else norm(got)==norm(exp); return [issue('EQUATION','PASS' if eq else 'FAIL' if eq is False else 'MANUAL_REVIEW','Tập nghiệm khớp.' if eq else 'Tập nghiệm không khớp.' if eq is False else 'Cần duyệt tập nghiệm.',f'computed={got}; expected={exp}')]
  if k=='mcq_index':
   ok=int(c['correct_index'])==int(q.get('answer_index',-1)); return [issue('MCQ_INDEX','PASS' if ok else 'FAIL','Chỉ số đáp án khớp.' if ok else 'Chỉ số đáp án sai.')]
  if k=='true_false':
   ok=c.get('truth_values')==q.get('answers'); return [issue('TF','PASS' if ok else 'FAIL','Bộ Đúng/Sai khớp.' if ok else 'Bộ Đúng/Sai không khớp.')]
  return [issue('UNKNOWN_CHECK','MANUAL_REVIEW',f'Chưa hỗ trợ check={k}.')]
 except Exception as e:return [issue('MATH_EXCEPTION','MANUAL_REVIEW','Không thể kiểm chứng tự động.',str(e),'Giáo viên duyệt thủ công.')]

def question_audit(q):
 issues=[]; typ=str(q.get('type','multiple_choice')).lower()
 if not q.get('question'): issues.append(issue('EMPTY','FAIL','Thiếu nội dung câu hỏi.'))
 if typ in ('multiple_choice','mcq'):
  o=q.get('options');
  if not isinstance(o,list) or len(o)!=4: issues.append(issue('OPTIONS','FAIL','MCQ phải có đúng 4 phương án.'))
  else:
   c=[norm(x) for x in o]
   if any(not x for x in c): issues.append(issue('EMPTY_OPTION','FAIL','Có phương án trống.'))
   if len(set(c))<4: issues.append(issue('DUP_OPTION','FAIL','Có phương án trùng.'))
  try:
   if int(q.get('answer_index',-1)) not in range(4): raise ValueError
  except: issues.append(issue('ANSWER_INDEX','FAIL','answer_index phải là 0–3.'))
 elif typ in ('true_false','truefalse','dung_sai'):
  if len(q.get('statements',q.get('options',[])))!=4: issues.append(issue('TF_COUNT','FAIL','Đúng/Sai phải có 4 mệnh đề.'))
 elif typ in ('short_answer','short','tra_loi_ngan') and q.get('expected_answer') in (None,''): issues.append(issue('SHORT','FAIL','Thiếu đáp án trả lời ngắn.'))
 issues += math_check(q)
 if typ in ('multiple_choice','mcq') and isinstance(q.get('options'),list) and len(q['options'])==4 and q.get('expected_answer') not in (None,''):
  hits=[]
  for i,o in enumerate(q['options']):
   e=equal(o,q['expected_answer']); a,b=num(o),num(q['expected_answer'])
   if e is True or (a is not None and b is not None and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9)): hits.append(i)
  if len(hits)==0: issues.append(issue('NO_CORRECT','FAIL','Không có phương án đúng theo expected_answer.'))
  elif len(hits)>1: issues.append(issue('MULTI_CORRECT','FAIL','Có nhiều phương án đúng.',str(hits)))
  else:
    try: selected=int(q.get('answer_index',-1))
    except: selected=-1
    if selected!=hits[0]: issues.append(issue('INDEX_MISMATCH','FAIL','answer_index không trỏ tới đáp án đã kiểm chứng.',f'expected={hits[0]}'))
 expr=(q.get('check') or {}).get('expression') or q.get('expression')
 if expr:
  try: issues.append(issue('DOMAIN','PASS','Đã phân tích miền xác định.',str(sp.calculus.util.continuous_domain(sx(expr),sp.Symbol('x'),sp.S.Reals))))
  except: issues.append(issue('DOMAIN','MANUAL_REVIEW','Không xác định được miền tự động.'))
 st='FAIL' if any(x['severity']=='FAIL' for x in issues) else 'MANUAL_REVIEW' if any(x['severity']=='MANUAL_REVIEW' for x in issues) else 'PASS'
 return {'status':st,'issues':issues}

def audit_exam(exam):
 qs=exam.get('questions',[]) if isinstance(exam,dict) else []; exam_issues=[]
 bp=exam.get('blueprint',{}) if isinstance(exam,dict) else {}
 if bp.get('total_questions') is not None and int(bp['total_questions'])!=len(qs): exam_issues.append(issue('BP_TOTAL','FAIL','Số câu không khớp ma trận.'))
 for field in ('type_distribution','level_distribution','topic_distribution'):
  for key,want in (bp.get(field,{}) or {}).items():
   got=sum(1 for q in qs if str(q.get('type','multiple_choice') if field=='type_distribution' else q.get('level','') if field=='level_distribution' else q.get('topic','')).lower()==str(key).lower())
   if int(want)!=got: exam_issues.append(issue('BP_'+field.upper(),'FAIL',f'Phân bố {field} {key} không khớp.',f'expected={want}; actual={got}'))
 seen=defaultdict(list)
 for i,q in enumerate(qs,1): seen[norm(q.get('question'))].append(i)
 for v in seen.values():
  if len(v)>1: exam_issues.append(issue('DUPLICATE','FAIL','Trùng nội dung câu hỏi.',str(v)))
 for i in range(len(qs)):
  for j in range(i+1,len(qs)):
   a,b=norm(qs[i].get('question')),norm(qs[j].get('question'))
   if a and b and SequenceMatcher(None,a,b).ratio()>=.88: exam_issues.append(issue('NEAR_DUPLICATE','MANUAL_REVIEW','Hai câu gần trùng, cần giáo viên duyệt.',f'Q{i+1}/Q{j+1}'))
 rows=[]
 for i,q in enumerate(qs,1):
  a=question_audit(q); rows.append({'number':i,'level':q.get('level',''),'topic':q.get('topic',''),'status':a['status'],'issues':a['issues']})
 c=Counter(r['status'] for r in rows); fail=c['FAIL']; manual=c['MANUAL_REVIEW']; passed=c['PASS']; total=len(rows)
 status='FAIL' if fail or any(x['severity']=='FAIL' for x in exam_issues) else 'MANUAL_REVIEW' if manual or any(x['severity']=='MANUAL_REVIEW' for x in exam_issues) else 'PASS'
 score=round(max(0,100*passed/max(1,total)-5*sum(x['severity']=='FAIL' for x in exam_issues)-2*sum(x['severity']=='MANUAL_REVIEW' for x in exam_issues)),1)
 return {'status':status,'summary':{'total':total,'pass':passed,'fail':fail,'manual_review':manual,'score':score},'exam_issues':exam_issues,'questions':rows}

def safe_autofix(exam):
 out=json.loads(json.dumps(exam,ensure_ascii=False)); changes=[]
 for i,q in enumerate(out.get('questions',[]),1):
  if isinstance(q.get('answer_index'),str) and q['answer_index'].strip().upper() in 'ABCD': q['answer_index']='ABCD'.index(q['answer_index'].strip().upper()); changes.append(f'Q{i}: chuẩn hóa A/B/C/D')
  o=q.get('options'); exp=q.get('expected_answer')
  if isinstance(o,list) and len(o)==4 and exp not in (None,''):
   hits=[k for k,x in enumerate(o) if equal(x,exp) is True or (num(x) is not None and num(exp) is not None and math.isclose(num(x),num(exp),rel_tol=1e-9,abs_tol=1e-9))]
   if len(hits)==1 and q.get('answer_index')!=hits[0]: q['answer_index']=hits[0]; changes.append(f'Q{i}: đồng bộ answer_index={hits[0]}')
 return out,changes

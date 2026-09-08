"""CTGDPT 2018 lesson profile and storyboard normalization/audit."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

PHASES=("KHỞI ĐỘNG","HÌNH THÀNH KIẾN THỨC","LUYỆN TẬP","VẬN DỤNG","CỦNG CỐ")
COMPETENCIES={
    "tư duy và lập luận toán học","mô hình hóa toán học","giải quyết vấn đề toán học",
    "giao tiếp toán học","sử dụng công cụ, phương tiện học toán",
}

def _text(value: Any, limit: int=1600) -> str:
    return re.sub(r"\s+"," ",str(value or "")).strip()[:limit]

def _list(value: Any, limit: int=12, item_limit: int=800) -> list[str]:
    if not isinstance(value,list): value=[] if value in (None,"") else [value]
    return [_text(x,item_limit) for x in value[:limit] if _text(x,item_limit)]

def normalize_profile(value: Any) -> dict:
    raw=value if isinstance(value,dict) else {}
    outcomes=[]
    for item in raw.get("learning_outcomes",[]) if isinstance(raw.get("learning_outcomes",[]),list) else []:
        if not isinstance(item,dict): continue
        outcomes.append({
            "outcome":_text(item.get("outcome"),500),
            "cognitive_level":_text(item.get("cognitive_level"),60).lower(),
            "math_competency":_text(item.get("math_competency"),120).lower(),
            "evidence":_text(item.get("evidence"),500),
            "assessment":_text(item.get("assessment"),500),
        })
    return {
        "lesson_position":_text(raw.get("lesson_position"),500),
        "source_scope":_text(raw.get("source_scope"),500),
        "prerequisites":_list(raw.get("prerequisites")),
        "learning_outcomes":outcomes[:10],
        "core_knowledge":_list(raw.get("core_knowledge")),
        "common_misconceptions":_list(raw.get("common_misconceptions")),
        "exclusions":_list(raw.get("exclusions")),
        "equipment":_list(raw.get("equipment")),
    }

def normalize_storyboard(value: Any) -> list[dict]:
    rows=[]
    for raw in value if isinstance(value,list) else []:
        if not isinstance(raw,dict): continue
        try: minutes=max(1,min(180,int(raw.get("minutes",1))))
        except (TypeError,ValueError): minutes=1
        phase=_text(raw.get("phase"),80).upper()
        refs=raw.get("slide_refs",[])
        if not isinstance(refs,list): refs=[]
        rows.append({
            "phase":phase if phase in PHASES else "HÌNH THÀNH KIẾN THỨC",
            "title":_text(raw.get("title"),240), "minutes":minutes,
            "objective":_text(raw.get("objective"),600),
            "organization":_text(raw.get("organization"),500),
            "student_task":_text(raw.get("student_task"),800),
            "product":_text(raw.get("product"),600),
            "assessment":_text(raw.get("assessment"),600),
            "guiding_questions":_list(raw.get("guiding_questions"),6,500),
            "anticipated_difficulties":_list(raw.get("anticipated_difficulties"),5,500),
            "support":_list(raw.get("support"),5,500),
            "conclusion":_text(raw.get("conclusion"),700),
            "slide_refs":[int(x) for x in refs if isinstance(x,int) and x>0][:30],
        })
    return rows[:30]

def audit_curriculum(profile: dict, storyboard: list[dict], periods: int, slide_count: int) -> dict:
    issues=[]; target=max(1,int(periods))*45; total=sum(x.get("minutes",0) for x in storyboard)
    def add(severity,code,message,evidence=""):
        issues.append({"severity":severity,"code":code,"message":message,"evidence":evidence})
    if not profile.get("source_scope"): add("FAIL","PROFILE_SOURCE","Hồ sơ chưa xác định phạm vi nguồn.")
    if not profile.get("core_knowledge"): add("FAIL","PROFILE_CORE","Hồ sơ chưa xác định kiến thức cốt lõi.")
    outcomes=profile.get("learning_outcomes",[])
    if not outcomes: add("FAIL","PROFILE_OUTCOMES","Chưa có yêu cầu cần đạt có cấu trúc.")
    for i,o in enumerate(outcomes,1):
        if not o.get("outcome") or not o.get("evidence") or not o.get("assessment"):
            add("FAIL","OUTCOME_EVIDENCE",f"Yêu cầu cần đạt {i} thiếu kết quả, minh chứng hoặc cách đánh giá.")
        comp=o.get("math_competency","")
        if comp and comp not in COMPETENCIES: add("REVIEW","COMPETENCY",f"Năng lực ở mục tiêu {i} cần giáo viên duyệt.",comp)
    if not storyboard: add("FAIL","STORYBOARD_EMPTY","Chưa có storyboard bài dạy.")
    phases=Counter(x.get("phase") for x in storyboard)
    for phase in PHASES:
        if not phases[phase]: add("FAIL","STORYBOARD_PHASE",f"Thiếu hoạt động {phase}.")
    if abs(total-target)>5: add("FAIL","TIME_BUDGET",f"Tổng thời gian {total} phút không khớp {target} phút ({periods} tiết).")
    elif total!=target: add("REVIEW","TIME_TOLERANCE",f"Tổng thời gian {total} phút; mục tiêu {target} phút.")
    used_refs=[]
    for i,row in enumerate(storyboard,1):
        required=("title","objective","organization","student_task","product","assessment","conclusion")
        missing=[k for k in required if not row.get(k)]
        if missing: add("FAIL","ACTIVITY_FIELDS",f"Hoạt động {i} thiếu: {', '.join(missing)}.")
        if not row.get("guiding_questions"): add("REVIEW","GUIDING_QUESTIONS",f"Hoạt động {i} chưa có câu hỏi gợi mở.")
        if not row.get("support"): add("REVIEW","DIFFERENTIATION",f"Hoạt động {i} chưa có phương án hỗ trợ học sinh.")
        for ref in row.get("slide_refs",[]):
            used_refs.append(ref)
            if ref>slide_count: add("FAIL","SLIDE_REF",f"Hoạt động {i} tham chiếu slide {ref} nhưng bài chỉ có {slide_count} slide.")
    if slide_count and not used_refs: add("REVIEW","SLIDE_LINKAGE","Storyboard chưa liên kết với các slide.")
    status="FAIL" if any(x["severity"]=="FAIL" for x in issues) else "REVIEW" if issues else "PASS"
    score=max(0,100-12*sum(x["severity"]=="FAIL" for x in issues)-4*sum(x["severity"]=="REVIEW" for x in issues))
    return {"version":"8.0.2","status":status,"score":score,"target_minutes":target,"total_minutes":total,"phase_counts":dict(phases),"issues":issues}


def structural_defects(lesson_report: dict, curriculum_report: dict, expected_slides: int) -> list[str]:
    """Return repairable generation defects; mathematical content is never auto-invented here."""
    defects=[]
    actual=int(lesson_report.get("summary",{}).get("slides",0))
    if abs(actual-int(expected_slides))>2:
        defects.append(f"Số slide hiện có {actual}; yêu cầu {expected_slides} (chấp nhận sai lệch tối đa 2).")
    lesson_codes={x.get("code") for x in lesson_report.get("issues",[])}
    curriculum_codes={x.get("code") for x in curriculum_report.get("issues",[])}
    if "MISSING_ACTIVITY" in lesson_codes or "STORYBOARD_PHASE" in curriculum_codes:
        defects.append("Thiếu một hoặc nhiều pha bắt buộc: KHỞI ĐỘNG, HÌNH THÀNH KIẾN THỨC, LUYỆN TẬP, VẬN DỤNG, CỦNG CỐ.")
    return defects


def repair_quality_key(lesson_report: dict, curriculum_report: dict, expected_slides: int) -> tuple[int,int,int]:
    issues=list(lesson_report.get("issues",[]))+list(curriculum_report.get("issues",[]))
    fails=sum(x.get("severity")=="FAIL" for x in issues)
    reviews=sum(x.get("severity")=="REVIEW" for x in issues)
    actual=int(lesson_report.get("summary",{}).get("slides",0))
    return fails,abs(actual-int(expected_slides)),reviews

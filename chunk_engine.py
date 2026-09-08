"""Utilities for deterministic 10-slide lesson assembly."""
from __future__ import annotations
import re
from typing import Any

def batch_range(completed: int, target: int, batch_size: int=10) -> tuple[int,int]:
    start=max(0,int(completed)); end=min(max(0,int(target)),start+max(1,int(batch_size)))
    return start+1,end

def compact_digest(slides: list[dict], limit: int=60) -> list[dict]:
    return [{"number":i,"title":str(s.get("title",""))[:180],"activity":str(s.get("activity","")),"knowledge":[str(x)[:220] for x in s.get("bullets",[])[:3]],"formulas":[str(x)[:160] for x in s.get("formulas",[])[:2]]} for i,s in enumerate(slides[:limit],1)]

def _tokens(value: Any) -> set[str]:
    return set(re.findall(r"[0-9a-zA-ZÀ-ỹ]+",str(value).lower()))

def similarity(a: dict,b: dict) -> float:
    x=_tokens(str(a.get("title",""))+" "+" ".join(a.get("bullets",[])[:3])); y=_tokens(str(b.get("title",""))+" "+" ".join(b.get("bullets",[])[:3]))
    return len(x&y)/len(x|y) if x|y else 0.0

def merge_unique(existing: list[dict], incoming: list[dict], threshold: float=.82) -> tuple[list[dict],list[str]]:
    merged=list(existing); rejected=[]
    for slide in incoming:
        duplicate=next((old for old in merged if similarity(old,slide)>=threshold),None)
        if duplicate:
            rejected.append(str(slide.get("title","Slide không tiêu đề")))
        else: merged.append(slide)
    return merged,rejected

def validate_plan(plan: Any,target: int) -> bool:
    if not isinstance(plan,list) or len(plan)!=int(target): return False
    numbers=[x.get("number") for x in plan if isinstance(x,dict)]
    titles=[str(x.get("title","")).strip().lower() for x in plan if isinstance(x,dict)]
    return numbers==list(range(1,int(target)+1)) and len(titles)==int(target) and all(titles) and len(set(titles))==len(titles)

def validate_source_batch(files: Any,max_files: int=8,max_total_bytes: int=50*1024*1024) -> tuple[bool,str]:
    items=list(files or [])
    if not items: return False,"Cần tải lên ít nhất một tài liệu nguồn."
    if len(items)>max_files: return False,f"Chỉ tải tối đa {max_files} tệp trong một bài giảng."
    total=sum(len(item.getvalue()) for item in items)
    if total>max_total_bytes: return False,"Tổng dung lượng các tệp vượt quá giới hạn."
    return True,""

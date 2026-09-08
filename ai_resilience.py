"""Resilient Gemini calls with conservative retry and model fallback."""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Iterable


class AIQuotaUnavailable(RuntimeError):
    """Raised after all usable models are rate-limited or unavailable."""


def classify_ai_error(exc: Exception) -> str:
    message=str(exc).lower()
    if "429" in message or "quota" in message or "resource_exhausted" in message:
        return "QUOTA"
    if "503" in message or "unavailable" in message or "overloaded" in message:
        return "TEMPORARY"
    if "api key" in message or "permission" in message or "403" in message:
        return "AUTH"
    return "OTHER"


def retry_delay_seconds(exc: Exception) -> float:
    message=str(exc)
    patterns=(r"retry_delay[^0-9]{0,20}(\d+(?:\.\d+)?)",r"retry in\s+(\d+(?:\.\d+)?)")
    for pattern in patterns:
        match=re.search(pattern,message,re.IGNORECASE)
        if match:
            return float(match.group(1))
    return 0.0


def order_models(selected: str, available: Iterable[str]) -> list[str]:
    models=[]
    for name in [selected,*available]:
        if name and name not in models and "gemini" in name.lower(): models.append(name)
    def rank(name: str) -> tuple[int,int]:
        low=name.lower()
        preferred=0 if name==selected else 1 if "flash-lite" in low else 2 if "flash" in low else 3
        deprecated=1 if "1.5" in low else 0
        return preferred,deprecated
    return sorted(models,key=rank)


def generate_with_fallback(
    selected_model: str,
    available_models: Iterable[str],
    contents: Any,
    model_factory: Callable[[str],Any],
    notify: Callable[[str],None] | None=None,
    sleep_fn: Callable[[float],None]=time.sleep,
    max_wait_seconds: float=35.0,
) -> tuple[Any,dict]:
    attempts=[]
    models=order_models(selected_model,available_models)
    if not models: raise AIQuotaUnavailable("Không có mô hình Gemini khả dụng.")
    for model_name in models:
        retried=False
        while True:
            try:
                response=model_factory(model_name).generate_content(contents)
                return response,{"used_model":model_name,"attempts":attempts,"fallback_used":model_name!=selected_model}
            except Exception as exc:
                kind=classify_ai_error(exc); delay=retry_delay_seconds(exc)
                attempts.append({"model":model_name,"error_type":kind,"message":str(exc)[:500]})
                daily="perday" in str(exc).lower() or "per day" in str(exc).lower()
                if kind in {"QUOTA","TEMPORARY"} and delay>0 and not daily and not retried:
                    wait=min(delay+1,max_wait_seconds)
                    if notify: notify(f"Mô hình {model_name} đang bận; hệ thống chờ {wait:.0f} giây rồi thử lại một lần.")
                    sleep_fn(wait); retried=True; continue
                if kind in {"QUOTA","TEMPORARY"}:
                    if notify: notify(f"Mô hình {model_name} chưa khả dụng; đang chuyển sang mô hình dự phòng.")
                    break
                if kind=="AUTH": raise
                break
    raise AIQuotaUnavailable("Các mô hình AI khả dụng đều đang hết hạn mức hoặc tạm thời quá tải. Dữ liệu đã nhập vẫn được giữ nguyên; vui lòng thử lại sau hoặc thay API Key.")

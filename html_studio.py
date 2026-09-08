"""Offline Image/Math Visual to HTML studio for LessonStudio."""
from __future__ import annotations

import base64
import html
import io
import json
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sympy as sp
from PIL import Image

from safe_math_parser import parse_math_expression
from visual_recovery_engine import build_variation_table


def image_data_uri(data: bytes, mime_type: str="image/png") -> str:
    if not data or len(data)>12*1024*1024: raise ValueError("Ảnh phải có dung lượng từ 1 byte đến 12 MB.")
    try:
        image=Image.open(io.BytesIO(data)); image.verify(); fmt=image.format
    except Exception as exc: raise ValueError("Tệp ảnh không hợp lệ.") from exc
    mime=Image.MIME.get(fmt,mime_type or "image/png")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def figure_html(data_uri: str, alt: str, caption: str="", max_width: int=900, object_fit: str="contain") -> str:
    width=max(240,min(1600,int(max_width))); fit=object_fit if object_fit in {"contain","cover","fill"} else "contain"
    safe_alt=html.escape(str(alt or "Minh họa Toán học"),quote=True)
    safe_caption=html.escape(str(caption or ""))
    cap=f"<figcaption>{safe_caption}</figcaption>" if safe_caption else ""
    return (f'<figure class="mathviz-figure"><img src="{data_uri}" alt="{safe_alt}" '
            f'style="display:block;width:100%;max-width:{width}px;height:auto;object-fit:{fit};margin:auto">{cap}</figure>')


def standalone_html(body: str, title: str="MathViz") -> str:
    safe_title=html.escape(title)
    return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title><style>
body{{margin:0;padding:24px;font-family:Arial,sans-serif;color:#17324d;background:#f5f9fc}}main{{max-width:1000px;margin:auto;background:white;padding:24px;border-radius:16px;box-shadow:0 8px 30px #17324d18}}.mathviz-figure{{margin:0;text-align:center}}figcaption{{margin-top:10px;font-size:15px;color:#526575}}table{{border-collapse:collapse;width:100%;font-family:"Cambria Math",serif}}th,td{{border:1px solid #345;padding:10px;text-align:center}}th{{background:#eaf6f8}}.up{{color:#087f8c;font-size:24px}}.down{{color:#b23a48;font-size:24px}}
</style></head><body><main>{body}</main></body></html>'''


def graph_png(expression: str, x_min: float=-5, x_max: float=5) -> bytes:
    if not x_min<x_max: raise ValueError("x_min phải nhỏ hơn x_max.")
    x_symbol=sp.Symbol("x",real=True); expr=parse_math_expression(expression,{"x":x_symbol})
    fn=sp.lambdify(x_symbol,expr,modules=[{"Abs":np.abs},"numpy"]); xs=np.linspace(float(x_min),float(x_max),1600)
    with np.errstate(all="ignore"): ys=np.asarray(fn(xs),dtype=float)
    if ys.ndim==0: ys=np.full_like(xs,float(ys))
    finite=np.isfinite(ys)
    if not finite.any(): raise ValueError("Không có giá trị hữu hạn trong khoảng vẽ.")
    vals=ys[finite]; lo,hi=np.percentile(vals,[1,99]); span=max(4.0,float(hi-lo)); plot=ys.copy()
    jumps=np.zeros_like(plot,dtype=bool); jumps[1:]=np.abs(np.diff(plot))>span*.8
    plot[~finite|jumps|(plot<lo-span)|(plot>hi+span)]=np.nan
    fig,ax=plt.subplots(figsize=(9,5)); ax.plot(xs,plot,color="#087f8c",lw=2.5); ax.axhline(0,color="#263238",lw=1); ax.axvline(0,color="#263238",lw=1)
    ax.grid(True,ls="--",alpha=.25); ax.set_xlim(x_min,x_max); ax.set_ylim(lo-span*.15,hi+span*.15); ax.set_title(f"Đồ thị y = {expression}",weight="bold")
    fig.tight_layout(); out=io.BytesIO(); fig.savefig(out,format="png",dpi=220,facecolor="white"); plt.close(fig); return out.getvalue()


def variation_table_html(table: dict[str,Any]) -> str:
    points=table.get("points",[]); signs=table.get("interval_signs",[]); values=table.get("values",[])
    if len(points)<2 or len(signs)!=len(points)-1 or len(values)!=len(points): raise ValueError("Dữ liệu bảng biến thiên không khớp.")
    xcells=[]; dcells=[]; ycells=[]
    for i,p in enumerate(points):
        xcells.append(f"<td>{html.escape(str(p))}</td>"); ycells.append(f"<td>{html.escape(str(values[i]))}</td>")
        dcells.append("<td></td>")
        if i<len(signs):
            sign=html.escape(str(signs[i])); arrow="↗" if sign=="+" else "↘" if sign=="-" else "→"
            xcells.append("<td></td>"); dcells.append(f"<td>{sign}</td>"); ycells.append(f'<td class="{"up" if sign=="+" else "down"}">{arrow}</td>')
    return f'<table aria-label="Bảng biến thiên"><tr><th>x</th>{"".join(xcells)}</tr><tr><th>f′(x)</th>{"".join(dcells)[:]}</tr><tr><th>f(x)</th>{"".join(ycells)}</tr></table>'


def visual_from_json(payload: str) -> tuple[str,str]:
    data=json.loads(payload)
    if "points" in data and "interval_signs" in data:
        body=variation_table_html(data); return body,standalone_html(body,"Bảng biến thiên")
    if "expression" in data:
        png=graph_png(str(data["expression"]),float(data.get("x_min",-5)),float(data.get("x_max",5)))
        body=figure_html(image_data_uri(png),str(data.get("caption") or "Đồ thị hàm số")); return body,standalone_html(body,"Đồ thị hàm số")
    raise ValueError("JSON phải là graph hoặc variation_table của LessonStudio.")


def render_html_studio(st) -> None:
    st.title("🖼️ Xưởng Ảnh → HTML")
    st.caption("Tải ảnh hoặc dựng trực quan Toán học, sau đó sao chép thẻ nhúng hay tải trang HTML độc lập.")
    tab_img,tab_graph,tab_table,tab_json=st.tabs(["Nhúng ảnh","Đồ thị hàm số","Bảng biến thiên","JSON → visual"])
    with tab_img:
        uploaded=st.file_uploader("Ảnh gốc (PNG, JPG/JPEG, WEBP)",type=["png","jpg","jpeg","webp"],key="html_image")
        col1,col2=st.columns(2); alt=col1.text_input("Văn bản thay thế",value="Minh họa Toán học"); caption=col2.text_input("Chú thích")
        width=st.select_slider("Chiều rộng tối đa",options=[480,640,720,900,1200],value=900)
        if uploaded:
            try:
                body=figure_html(image_data_uri(uploaded.getvalue(),uploaded.type),alt,caption,width); document=standalone_html(body,caption or "Minh họa Toán học")
                st.components.v1.html(document,height=520,scrolling=True); st.code(body,language="html")
                st.download_button("⬇️ TẢI HTML",document,"mathviz_image.html","text/html",use_container_width=True)
            except ValueError as exc: st.error(str(exc))
    with tab_graph:
        expression=st.text_input("Hàm số — dùng * và **",value="x**3-3*x+2",key="html_graph_expr")
        c1,c2=st.columns(2); x_min=c1.number_input("x_min",value=-5.0); x_max=c2.number_input("x_max",value=5.0)
        if st.button("DỰNG ĐỒ THỊ HTML",key="make_html_graph",use_container_width=True):
            try:
                png=graph_png(expression,x_min,x_max); body=figure_html(image_data_uri(png),f"Đồ thị y = {expression}",f"Đồ thị y = {expression}")
                document=standalone_html(body,"Đồ thị hàm số"); st.session_state["html_graph_result"]=(body,document)
            except Exception as exc: st.error(f"Không dựng được đồ thị: {exc}")
        if st.session_state.get("html_graph_result"):
            body,document=st.session_state["html_graph_result"]; st.components.v1.html(document,height=540,scrolling=True); st.code(body,language="html"); st.download_button("⬇️ TẢI HTML ĐỒ THỊ",document,"mathviz_graph.html","text/html",use_container_width=True)
    with tab_table:
        expression=st.text_input("Biểu thức để tự dựng bảng",value="x**3-3*x",key="html_table_expr")
        if st.button("DỰNG BẢNG BIẾN THIÊN HTML",key="make_html_table",use_container_width=True):
            table,detail=build_variation_table(expression)
            if not table: st.error(detail)
            else:
                body=variation_table_html(table); st.session_state["html_table_result"]=(body,standalone_html(body,"Bảng biến thiên"),table)
        if st.session_state.get("html_table_result"):
            body,document,table=st.session_state["html_table_result"]; st.json(table); st.components.v1.html(document,height=300,scrolling=True); st.code(body,language="html"); st.download_button("⬇️ TẢI HTML BẢNG BIẾN THIÊN",document,"mathviz_variation_table.html","text/html",use_container_width=True)
    with tab_json:
        payload=st.text_area("Dán graph hoặc variation_table JSON",height=220,placeholder='{"expression":"x**2","x_min":-5,"x_max":5}')
        if st.button("CHUYỂN JSON THÀNH HTML",key="json_to_html",use_container_width=True) and payload.strip():
            try: st.session_state["html_json_result"]=visual_from_json(payload)
            except Exception as exc: st.error(f"JSON không hợp lệ: {exc}")
        if st.session_state.get("html_json_result"):
            body,document=st.session_state["html_json_result"]; st.components.v1.html(document,height=520,scrolling=True); st.code(body,language="html"); st.download_button("⬇️ TẢI HTML",document,"mathviz_from_json.html","text/html",use_container_width=True)

import json
import io
import re
import streamlit as st
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import docx
import google.generativeai as genai

# CẤU HÌNH TRANG WEB
st.set_page_config(page_title="Soạn PowerPoint Tự Động", layout="wide")
st.title("📚 Trợ Lý Soạn Giáo Án PowerPoint Tự Động")

# LẤY KHÓA VÀ QUÉT MÔ HÌNH
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    API_KEY = ""
    st.error("Chưa tìm thấy khóa API trong mục Secrets!")

with st.sidebar:
    st.header("⚙️ Cấu hình hệ thống")
    if API_KEY:
        st.success("✅ Đã nhận cấu hình API Key từ Secrets!")
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if available_models:
                selected_model = st.selectbox("🤖 Chọn mô hình AI:", available_models)
            else:
                st.error("Tài khoản chưa được cấp quyền dùng AI.")
                selected_model = None
        except Exception as e:
            st.error("Lỗi khi kết nối lấy danh sách AI.")
            selected_model = None
    else:
        st.error("❌ Thiếu API Key!")
        selected_model = None

# 1. HÀM TẠO POWERPOINT TỰ ĐỘNG
def xuat_powerpoint(noi_dung_bai_hoc, file_ra="GiaoAn_Output.pptx"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    slide_title = prs.slides.add_slide(blank_layout)
    tx = slide_title.shapes.add_textbox(Inches(1), Inches(2.2), Inches(11.333), Inches(3))
    p = tx.text_frame.paragraphs[0]
    p.text = str(noi_dung_bai_hoc.get("tieu_de", "Bài Giảng Điện Tử"))
    p.font.size = Pt(38)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0, 51, 102)
    p.alignment = PP_ALIGN.CENTER

    p2 = tx.text_frame.add_paragraph()
    p2.text = f"Môn: {noi_dung_bai_hoc.get('mon', 'Toán học')} | Giáo viên: {noi_dung_bai_hoc.get('giao_vien', 'Hồ Thuyết Dũng')}"
    p2.font.size = Pt(22)
    p2.font.color.rgb = RGBColor(100, 100, 100)
    p2.alignment = PP_ALIGN.CENTER

    for item in noi_dung_bai_hoc.get("cac_slide", []):
        slide = prs.slides.add_slide(blank_layout)
        
        t_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.7), Inches(0.8))
        p_t = t_box.text_frame.paragraphs[0]
        p_t.text = str(item.get("tieu_de_slide", ""))
        p_t.font.size = Pt(28)
        p_t.font.bold = True
        p_t.font.color.rgb = RGBColor(0, 51, 102)

        c_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5))
        tf_c = c_box.text_frame
        tf_c.word_wrap = True
        
        for idx, bullet in enumerate(item.get("noi_dung", [])):
            p_c = tf_c.paragraphs[0] if idx == 0 else tf_c.add_paragraph()
            p_c.text = f"• {bullet}"
            p_c.font.size = Pt(20)
            p_c.font.color.rgb = RGBColor(50, 50, 50)
            p_c.space_after = Pt(14)

    prs.save(file_ra)
    return file_ra

# 2. HÀM GỌI AI PHÂN TÍCH TÀI LIỆU
def phan_tich_tai_lieu_ai(file_tai_len, ai_model):
    file_bytes = file_tai_len.getvalue()
    ten_file = file_tai_len.name.lower()

    prompt = """
    Bạn là chuyên gia sư phạm môn Toán. Hãy thiết kế bài giảng PowerPoint từ tài liệu gốc.
    ĐỂ TRÁNH LỖI BẢN QUYỀN (RECITATION), BẮT BUỘC PHẢI THỰC HIỆN:
    - KHÔNG chép phạt y nguyên định lý. Hãy chuyển hóa thành ngôn ngữ giảng dạy tương tác (Ví dụ: "Các em lưu ý quy tắc sau...", "Thầy có một ví dụ nhỏ...").
    - Tự động bổ sung thêm các câu hỏi gợi mở, ghi chú sư phạm, hoặc ví dụ thực tế vào mỗi slide để làm mới hoàn toàn đoạn văn bản gốc.
    - LƯU Ý JSON: Mọi công thức Toán học (LaTeX) chứa dấu gạch chéo ngược (\) BẮT BUỘC phải được nhân đôi thành (\\\\) (Ví dụ: \\\\frac, \\\\lim).
    - Xuất ra DUY NHẤT định dạng JSON thuần:
    {
        "tieu_de": "Tên bài học",
        "mon": "Toán học",
        "giao_vien": "Hồ Thuyết Dũng",
        "cac_slide": [
            {
                "tieu_de_slide": "Tiêu đề Slide",
                "noi_dung": [
                    "Câu hỏi dẫn dắt hoặc ghi chú...",
                    "Nội dung kiến thức (đã được diễn giải lại)..."
                ]
            }
        ]
    }
    """

    if ten_file.endswith(".pdf"):
        noi_dung_input = [{"mime_type": "application/pdf", "data": file_bytes}, prompt]
    elif ten_file.endswith(".docx"):
        doc = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join([p.text for p in doc.paragraphs if p.text])
        noi_dung_input = [f"Nội dung tài liệu:\n{text[:10000]}\n\n{prompt}"]
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
        noi_dung_input = [f"Nội dung tài liệu:\n{text[:10000]}\n\n{prompt}"]

    model = genai.GenerativeModel(ai_model, generation_config={"response_mime_type": "application/json"})
    response = model.generate_content(noi_dung_input)
    
    # Bộ lọc sửa lỗi JSON do công thức Toán học gây ra
    raw_json = response.text
    try:
        return json.loads(raw_json, strict=False)
    except Exception:
        fixed_json = raw_json.replace('\\', '\\\\')
        fixed_json = fixed_json.replace('\\\\"', '\\"')
        fixed_json = fixed_json.replace('\\\\n', '\\n')
        fixed_json = fixed_json.replace('\\\\t', '\\t')
        return json.loads(fixed_json, strict=False)

# GIAO DIỆN CHÍNH
st.write("Chọn tài liệu bài giảng nguồn (PDF, Word hoặc TXT) để tự động soạn Slide:")
file_tai_len = st.file_uploader("Tải tài liệu lên", type=["pdf", "docx", "txt"], label_visibility="collapsed")

if file_tai_len and selected_model:
    if st.button("🚀 Bắt đầu soạn giáo án tự động"):
        with st.spinner(f"AI ({selected_model}) đang đọc tài liệu và thiết kế giáo án... Thầy vui lòng chờ giây lát..."):
            try:
                du_lieu_json = phan_tich_tai_lieu_ai(file_tai_len, selected_model)
                file_ppt = xuat_powerpoint(du_lieu_json)
                st.success("🎉 Đã soạn xong bài giảng PowerPoint!")

                with open(file_ppt, "rb") as f:
                    st.download_button(
                        label="📥 Bấm vào đây để tải bài giảng về máy (.pptx)",
                        data=f,
                        file_name="GiaoAn_SoanTuDong.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
            except Exception as e:
                st.error(f"Lỗi khi phân tích: {str(e)}")

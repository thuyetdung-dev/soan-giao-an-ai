import json
import time
import io
import streamlit as st
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from google import genai
from google.genai import types
import docx

# CẤU HÌNH TRANG WEB
st.set_page_config(page_title="Soạn PowerPoint Tự Động", layout="wide")
st.title("📚 Trợ Lý Soạn Giáo Án PowerPoint Tự Động")

# GẮN TRỰC TIẾP API KEY CỦA THẦY VÀO ĐÂY
API_KEY = "AIzaSyBKfKYlRp81PB94OHslXZmT37MDHLcO8lM"

with st.sidebar:
    st.header("⚙️ Cấu hình hệ thống")
    st.success("✅ Đã kết nối Gemini API thành công!")

# 1. HÀM TẠO POWERPOINT TỰ ĐỘNG
def xuat_powerpoint(noi_dung_bai_hoc, file_ra="GiaoAn_Output.pptx"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Slide tiêu đề
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

    # Các slide nội dung
    for item in noi_dung_bai_hoc.get("cac_slide", []):
        slide = prs.slides.add_slide(blank_layout)
        
        # Tiêu đề slide
        t_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.7), Inches(0.8))
        p_t = t_box.text_frame.paragraphs[0]
        p_t.text = str(item.get("tieu_de_slide", ""))
        p_t.font.size = Pt(28)
        p_t.font.bold = True
        p_t.font.color.rgb = RGBColor(0, 51, 102)

        # Nội dung bullet
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

# 2. HÀM GỌI AI PHÂN TÍCH TÀI LIỆU (CÓ TỰ ĐỘNG THỬ LẠI NẾU MÁY CHỦ BẬN)
def phan_tich_tai_lieu_ai(file_tai_len, key):
    client = genai.Client(api_key=key)
    file_bytes = file_tai_len.getvalue()
    ten_file = file_tai_len.name.lower()

    prompt = """
    Bạn là chuyên gia sư phạm. Hãy phân tích tài liệu được cung cấp và thiết kế cấu trúc bài giảng PowerPoint chuẩn mực từ 4 đến 7 slide.
    Xuất ra DUY NHẤT định dạng JSON thuần (không kèm bất kỳ văn bản giải thích nào khác) theo mẫu sau:
    {
        "tieu_de": "Tên bài học",
        "mon": "Môn học",
        "giao_vien": "Tên giáo viên",
        "cac_slide": [
            {
                "tieu_de_slide": "Tiêu đề Slide",
                "noi_dung": ["Ý chính 1", "Ý chính 2", "Ý chính 3"]
            }
        ]
    }
    """

    if ten_file.endswith(".pdf"):
        noi_dung_input = [
            types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"),
            prompt
        ]
    elif ten_file.endswith(".docx"):
        doc = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join([p.text for p in doc.paragraphs if p.text])
        noi_dung_input = [f"Nội dung tài liệu:\n{text[:10000]}\n\n{prompt}"]
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
        noi_dung_input = [f"Nội dung tài liệu:\n{text[:10000]}\n\n{prompt}"]

    # Thử gọi tối đa 3 lần nếu máy chủ Google quá tải tạm thời (503)
    for lan_thu in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=noi_dung_input,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text)
        except Exception as e:
            if "503" in str(e) and lan_thu < 2:
                time.sleep(3)  # Chờ 3 giây rồi tự động thử lại
                continue
            raise e

    prompt = """
    Bạn là chuyên gia sư phạm. Hãy phân tích tài liệu được cung cấp và thiết kế cấu trúc bài giảng PowerPoint chuẩn mực từ 4 đến 7 slide.
    Xuất ra DUY NHẤT định dạng JSON thuần (không kèm bất kỳ văn bản giải thích nào khác) theo mẫu sau:
    {
        "tieu_de": "Tên bài học",
        "mon": "Môn học",
        "giao_vien": "Tên giáo viên",
        "cac_slide": [
            {
                "tieu_de_slide": "Tiêu đề Slide",
                "noi_dung": ["Ý chính 1", "Ý chính 2", "Ý chính 3"]
            }
        ]
    }
    """

    if ten_file.endswith(".pdf"):
        noi_dung_input = [
            types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"),
            prompt
        ]
    elif ten_file.endswith(".docx"):
        doc = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join([p.text for p in doc.paragraphs if p.text])
        noi_dung_input = [f"Nội dung tài liệu:\n{text[:10000]}\n\n{prompt}"]
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
        noi_dung_input = [f"Nội dung tài liệu:\n{text[:10000]}\n\n{prompt}"]

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=noi_dung_input,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)

# GIAO DIỆN CHÍNH
st.write("Chọn tài liệu bài giảng nguồn (PDF, Word hoặc TXT) để tự động soạn Slide:")
file_tai_len = st.file_uploader("Tải tài liệu lên", type=["pdf", "docx", "txt"], label_visibility="collapsed")

if file_tai_len:
    if st.button("🚀 Bắt đầu soạn giáo án tự động"):
        with st.spinner("AI đang đọc tài liệu và thiết kế giáo án... Thầy vui lòng chờ giây lát..."):
            try:
                du_lieu_json = phan_tich_tai_lieu_ai(file_tai_len, API_KEY)
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

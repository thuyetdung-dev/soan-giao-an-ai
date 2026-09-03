import json
import io
import streamlit as st
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import docx
import google.generativeai as genai

# CẤU HÌNH TRANG WEB
st.set_page_config(page_title="Soạn PowerPoint Tự Động", layout="wide")
st.title("📚 Trợ Lý Soạn Giáo Án PowerPoint Tự Động")

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

# HÀM VẼ BẢNG BIẾN THIÊN BẰNG MATPLOTLIB
def tao_anh_bbt(bbt_data):
    x_data = bbt_data.get("x", [])
    y_phay_data = bbt_data.get("y_phay", [])
    y_val_data = bbt_data.get("y_val", [])
    y_pos_data = bbt_data.get("y_pos", [])
    
    n = len(x_data)
    if n == 0: return None
    
    fig, ax = plt.subplots(figsize=(n * 1.2, 3))
    ax.axis('off')
    
    # Kẻ khung
    ax.plot([0, n+1], [2, 2], color='black', lw=1.2)
    ax.plot([0, n+1], [1, 1], color='black', lw=1.2)
    ax.plot([1, 1], [0, 3], color='black', lw=1.2)
    
    # Nhãn cột đầu
    ax.text(0.5, 2.5, 'x', ha='center', va='center', fontsize=16, style='italic')
    ax.text(0.5, 1.5, 'y\'', ha='center', va='center', fontsize=16, style='italic')
    ax.text(0.5, 0.5, 'y', ha='center', va='center', fontsize=16, style='italic')
    
    y_coords = []
    for i in range(n):
        col_x = 1.5 + i
        # Vẽ x
        if i < len(x_data) and x_data[i]: 
            ax.text(col_x, 2.5, str(x_data[i]), ha='center', va='center', fontsize=15)
            
        # Vẽ y' và đường không xác định (||)
        if i < len(y_phay_data):
            val_yp = str(y_phay_data[i])
            if val_yp == "||":
                ax.plot([col_x-0.03, col_x-0.03], [0, 2], color='black', lw=1)
                ax.plot([col_x+0.03, col_x+0.03], [0, 2], color='black', lw=1)
            elif val_yp: 
                ax.text(col_x, 1.5, val_yp, ha='center', va='center', fontsize=15)
                
        # Vẽ y
        if i < len(y_val_data) and y_val_data[i]:
            pos_str = y_pos_data[i] if i < len(y_pos_data) else "bot"
            pos = 0.85 if pos_str == "top" else 0.15
            y_coords.append((col_x, pos))
            ax.text(col_x, pos, str(y_val_data[i]), ha='center', va='center', fontsize=15)
    
    # Vẽ mũi tên vector
    for i in range(len(y_coords)-1):
        x1, y1 = y_coords[i]
        x2, y2 = y_coords[i+1]
        dx = x2 - x1
        dy = y2 - y1
        # Cắt ngắn mũi tên để không đè lên chữ
        ax.annotate("", xy=(x2 - 0.2*dx, y2 - 0.2*dy), 
                    xytext=(x1 + 0.2*dx, y1 + 0.2*dy),
                    arrowprops=dict(arrowstyle="->", color="black", lw=1.5))
                    
    ax.set_xlim(0, n+1)
    ax.set_ylim(0, 3)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, transparent=True)
    buf.seek(0)
    plt.close(fig)
    return buf

# HÀM TẠO POWERPOINT
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
        
        t_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.8))
        p_t = t_box.text_frame.paragraphs[0]
        p_t.text = str(item.get("tieu_de_slide", ""))
        p_t.font.size = Pt(28)
        p_t.font.bold = True
        p_t.font.color.rgb = RGBColor(0, 51, 102)

        bbt = item.get("bang_bien_thien")
        chieu_cao_chu_thich = Inches(5) if not bbt else Inches(2.5)
        
        c_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.2), Inches(11.7), chieu_cao_chu_thich)
        tf_c = c_box.text_frame
        tf_c.word_wrap = True
        
        for idx, bullet in enumerate(item.get("noi_dung", [])):
            p_c = tf_c.paragraphs[0] if idx == 0 else tf_c.add_paragraph()
            p_c.text = f"• {bullet}"
            p_c.font.size = Pt(20)
            p_c.font.color.rgb = RGBColor(50, 50, 50)
            p_c.space_after = Pt(10)

        # Chèn ảnh bảng biến thiên
        if bbt and isinstance(bbt, dict):
            buf = tao_anh_bbt(bbt)
            if buf:
                # Căn giữa ảnh ở nửa dưới slide
                slide.shapes.add_picture(buf, Inches(2), Inches(4), width=Inches(9))

    prs.save(file_ra)
    return file_ra

# HÀM GỌI AI PHÂN TÍCH TÀI LIỆU
def phan_tich_tai_lieu_ai(file_tai_len, ai_model):
    file_bytes = file_tai_len.getvalue()
    ten_file = file_tai_len.name.lower()

    prompt = """
    Bạn là chuyên gia sư phạm Toán. Thiết kế bài giảng PowerPoint chi tiết.
    
    LƯU Ý ĐỊNH DẠNG TEXT:
    - KHÔNG DÙNG MÃ LATEX. Dùng Unicode (x₁, x₂, ∞, ∈, ℝ, phân số viết ngang a/b).
    
    LƯU Ý VỀ BẢNG BIẾN THIÊN (MODULE ĐỒ HỌA MỚI):
    - Đã có module tự vẽ hình. Bạn phải cung cấp 4 mảng dữ liệu có CÙNG ĐỘ DÀI (rất quan trọng, phải xen kẽ giữa điểm và khoảng).
    - Các vị trí khoảng trống để "". Tại điểm không xác định dùng "||".
    - "y_pos" dùng để phần mềm biết tọa độ vẽ ("top" cho điểm ở trên, "bot" cho điểm ở dưới).
    - Ví dụ hàm số cực đại tại -1 (y=34), cực tiểu tại 3 (y=30):
        "bang_bien_thien": {
            "x":      ["-∞", "", "-1", "", "3", "", "+∞"],
            "y_phay": ["", "+", "0", "-", "0", "+", ""],
            "y_val":  ["-∞", "", "34", "", "30", "", "+∞"],
            "y_pos":  ["bot", "", "top", "", "bot", "", "top"] 
        }
    
    Xuất ra DUY NHẤT JSON thuần:
    {
        "tieu_de": "Tên bài học",
        "mon": "Toán học",
        "giao_vien": "Hồ Thuyết Dũng",
        "cac_slide": [
            {
                "tieu_de_slide": "Ví dụ bảng biến thiên",
                "noi_dung": ["Ta có bảng biến thiên sau:"],
                "bang_bien_thien": { ...như ví dụ trên... }
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
    
    raw_json = response.text
    try:
        return json.loads(raw_json, strict=False)
    except Exception:
        fixed_json = raw_json.replace('\\', '\\\\')
        return json.loads(fixed_json, strict=False)

# GIAO DIỆN CHÍNH
st.write("Chọn tài liệu bài giảng nguồn (PDF, Word hoặc TXT) để tự động soạn Slide:")
file_tai_len = st.file_uploader("Tải tài liệu lên", type=["pdf", "docx", "txt"], label_visibility="collapsed")

if file_tai_len and selected_model:
    if st.button("🚀 Bắt đầu soạn giáo án tự động"):
        with st.spinner(f"AI ({selected_model}) đang thiết kế giáo án và vẽ đồ họa bảng biến thiên..."):
            try:
                du_lieu_json = phan_tich_tai_lieu_ai(file_tai_len, selected_model)
                file_ppt = xuat_powerpoint(du_lieu_json)
                st.success("🎉 Đã soạn xong bài giảng PowerPoint!")

                with open(file_ppt, "rb") as f:
                    st.download_button(
                        label="📥 Tải bài giảng về máy (.pptx)",
                        data=f,
                        file_name="GiaoAn_ToanHoc_TuyetDep.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
            except Exception as e:
                st.error(f"Lỗi khi phân tích: {str(e)}")

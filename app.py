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

# HÀM VẼ BẢNG BIẾN THIÊN TỰ ĐỘNG SỬA LỖI TOÁN HỌC
def tao_anh_bbt(bbt_data):
    x_data = bbt_data.get("x", [])
    y_phay_data = bbt_data.get("y_phay", [])
    y_val_data = bbt_data.get("y_val", [])
    
    n = len(x_data)
    if n == 0: return None
    
    fig, ax = plt.subplots(figsize=(n * 1.2, 3))
    ax.axis('off')
    
    # Kẻ khung cơ bản
    ax.plot([0, n+1], [2, 2], color='black', lw=1.2)
    ax.plot([0, n+1], [1, 1], color='black', lw=1.2)
    ax.plot([1, 1], [0, 3], color='black', lw=1.2)
    
    ax.text(0.5, 2.5, 'x', ha='center', va='center', fontsize=16, style='italic')
    ax.text(0.5, 1.5, 'y\'', ha='center', va='center', fontsize=16, style='italic')
    ax.text(0.5, 0.5, 'y', ha='center', va='center', fontsize=16, style='italic')
    
    y_coords = []
    for i in range(n):
        col_x = 1.5 + i
        if i < len(x_data) and x_data[i]: 
            ax.text(col_x, 2.5, str(x_data[i]), ha='center', va='center', fontsize=15)
            
        # Lấy dấu đạo hàm xung quanh để tính toán độ dốc
        left_sign = str(y_phay_data[i-1]).strip() if i > 0 and i-1 < len(y_phay_data) else ""
        right_sign = str(y_phay_data[i+1]).strip() if i+1 < len(y_phay_data) else ""
        
        if i < len(y_phay_data):
            val_yp = str(y_phay_data[i]).strip()
            if val_yp == "||":
                ax.plot([col_x-0.03, col_x-0.03], [0, 2], color='black', lw=1.2)
                ax.plot([col_x+0.03, col_x+0.03], [0, 2], color='black', lw=1.2)
            elif val_yp: 
                ax.text(col_x, 1.5, val_yp, ha='center', va='center', fontsize=15)
                
        if i < len(y_val_data) and y_val_data[i]:
            val_y = str(y_val_data[i]).strip()
            
            # ÉP TỌA ĐỘ TOÁN HỌC THEO DẤU ĐẠO HÀM (Vượt qua ảo giác AI)
            if "||" in val_y:
                parts = val_y.split("||")
                if len(parts) == 2:
                    p1, p2 = parts[0].strip(), parts[1].strip()
                    # Nếu trước || là "-", đồ thị lao xuống đáy. Nếu "+", lao lên đỉnh.
                    pos1 = 0.15 if left_sign == "-" else 0.85
                    # Nếu sau || là "-", đồ thị bắt đầu từ đỉnh. Nếu "+", từ đáy.
                    pos2 = 0.85 if right_sign == "-" else 0.15
                    
                    ax.text(col_x - 0.25, pos1, p1, ha='right', va='center', fontsize=14)
                    ax.text(col_x + 0.25, pos2, p2, ha='left', va='center', fontsize=14)
                    y_coords.append((col_x - 0.25, pos1))
                    y_coords.append((col_x + 0.25, pos2))
                    continue

            # Các điểm cực trị và mút bình thường
            if left_sign == "+" or right_sign == "-": pos = 0.85  # Cực đại
            elif left_sign == "-" or right_sign == "+": pos = 0.15 # Cực tiểu
            else: pos = 0.5
            
            # Xử lý vô cực ở mút ngoài cùng
            if i == 0: pos = 0.15 if right_sign == "+" else 0.85
            if i == n - 1: pos = 0.85 if left_sign == "+" else 0.15

            y_coords.append((col_x, pos))
            ax.text(col_x, pos, val_y, ha='center', va='center', fontsize=15)
    
    # Vẽ mũi tên kết nối liên tục
    for i in range(len(y_coords)-1):
        x1, y1 = y_coords[i]
        x2, y2 = y_coords[i+1]
        
        if abs(x2 - x1) < 0.6: continue # Bỏ qua nét vẽ cắt ngang vách ||
        
        dx, dy = x2 - x1, y2 - y1
        sign_y = 1 if dy > 0 else (-1 if dy < 0 else 0.01) # Tránh lỗi chia 0
        shrink_x, shrink_y = 0.2, 0.2
        
        ax.annotate("", xy=(x2 - shrink_x, y2 - shrink_y * sign_y), 
                    xytext=(x1 + shrink_x, y1 + shrink_y * sign_y),
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

        if bbt and isinstance(bbt, dict):
            buf = tao_anh_bbt(bbt)
            if buf:
                slide.shapes.add_picture(buf, Inches(2.1), Inches(3.8), width=Inches(9))

    prs.save(file_ra)
    return file_ra

# HÀM GỌI AI PHÂN TÍCH TÀI LIỆU
def phan_tich_tai_lieu_ai(file_tai_len, ai_model):
    file_bytes = file_tai_len.getvalue()
    ten_file = file_tai_len.name.lower()

    prompt = """
    Bạn là chuyên gia sư phạm Toán. Thiết kế bài giảng PowerPoint chi tiết.
    
    LƯU Ý ĐỊNH DẠNG:
    - BẮT BUỘC Tách nhỏ nội dung: Mỗi khái niệm, định lý hoặc một ví dụ giải bài tập phải độc lập trên 1 slide riêng biệt.
    - Tính toán Toán học CHÍNH XÁC TUYỆT ĐỐI, đặc biệt là giới hạn (lim) của hàm phân thức tại tiệm cận đứng.
    - Dùng Unicode (x₁, x₂, ∞, ∈, ℝ, phân số viết ngang a/b). Không dùng LaTeX.
    
    LƯU Ý VỀ BẢNG BIẾN THIÊN:
    - Cung cấp 3 mảng dữ liệu CÙNG ĐỘ DÀI: "x", "y_phay", "y_val".
    - Các khoảng xen kẽ giữa các nghiệm hãy để khoảng trắng "". 
    - Tại điểm không xác định dùng "||". Tại dòng y, tách giới hạn 2 bên bằng "||".
    - Ví dụ hàm số y = (x² - 2x + 5)/(x - 1) với y'=0 tại -1 và 3, không xác định tại 1:
        "bang_bien_thien": {
            "x":      ["-∞", "", "-1", "", "1", "", "3", "", "+∞"],
            "y_phay": ["", "+", "0", "-", "||", "-", "0", "+", ""],
            "y_val":  ["-∞", "", "-4", "", "-∞ || +∞", "", "4", "", "+∞"]
        }
    
    Xuất ra DUY NHẤT JSON thuần.
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
                        file_name="GiaoAn_ToanHoc.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
            except Exception as e:
                st.error(f"Lỗi khi phân tích: {str(e)}")

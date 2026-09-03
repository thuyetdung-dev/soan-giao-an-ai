import json
import io
import re
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
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
                default_index = available_models.index('models/gemini-1.5-flash') if 'models/gemini-1.5-flash' in available_models else 0
                selected_model = st.selectbox("🤖 Chọn mô hình AI:", available_models, index=default_index)
            else:
                st.error("Tài khoản chưa được cấp quyền dùng AI.")
                selected_model = None
        except Exception as e:
            st.error("Lỗi khi kết nối lấy danh sách AI.")
            selected_model = None
    else:
        st.error("❌ Thiếu API Key!")
        selected_model = None

# 1. HÀM VẼ ĐỒ THỊ HÀM SỐ
def tao_anh_do_thi(bieu_thuc, x_min=-5, x_max=5):
    try:
        fig, ax = plt.subplots(figsize=(6, 4))
        x = np.linspace(x_min, x_max, 400)
        
        bieu_thuc = bieu_thuc.replace('^', '**')
        safe_dict = {"x": x, "np": np, "sin": np.sin, "cos": np.cos, "tan": np.tan, "sqrt": np.sqrt, "abs": np.abs, "exp": np.exp}
        y = eval(bieu_thuc, {"__builtins__": None}, safe_dict)
        
        ax.plot(x, y, color='blue', lw=2)
        
        ax.axhline(0, color='black', lw=1.2)
        ax.axvline(0, color='black', lw=1.2)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        y_min, y_max = np.nanmin(y), np.nanmax(y)
        if y_max - y_min > 50:
            ax.set_ylim(-20, 20)
            
        ax.set_title(f"Đồ thị: y = {bieu_thuc.replace('**', '^')}", fontsize=12)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, transparent=True)
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        plt.close(fig)
        return None

# 2. HÀM VẼ BẢNG XÉT DẤU VÀ BẢNG BIẾN THIÊN
def tao_anh_bbt(bbt_data, is_xet_dau=False):
    x_data = bbt_data.get("x", [])
    y_phay_data = bbt_data.get("y_phay", [])
    y_val_data = bbt_data.get("y_val", [])
    
    n = len(x_data)
    if n == 0: return None
    
    rows = 2 if is_xet_dau else 3
    fig, ax = plt.subplots(figsize=(n * 1.2, rows))
    ax.axis('off')
    
    for r in range(rows + 1):
        ax.plot([0, n+1], [r, r], color='black', lw=1.2)
    ax.plot([1, 1], [0, rows], color='black', lw=1.2)
    
    ax.text(0.5, rows - 0.5, 'x', ha='center', va='center', fontsize=16, style='italic')
    ax.text(0.5, rows - 1.5, 'y\'', ha='center', va='center', fontsize=16, style='italic')
    if not is_xet_dau:
        ax.text(0.5, 0.5, 'y', ha='center', va='center', fontsize=16, style='italic')
    
    y_coords = []
    for i in range(n):
        col_x = 1.5 + i
        if i < len(x_data) and x_data[i]: 
            ax.text(col_x, rows - 0.5, str(x_data[i]), ha='center', va='center', fontsize=15)
            
        left_sign = str(y_phay_data[i-1]).strip() if i > 0 and i-1 < len(y_phay_data) else ""
        right_sign = str(y_phay_data[i+1]).strip() if i+1 < len(y_phay_data) else ""
        
        if i < len(y_phay_data):
            val_yp = str(y_phay_data[i]).strip()
            if val_yp == "||":
                ax.plot([col_x-0.03, col_x-0.03], [0, rows - 1], color='black', lw=1.2)
                ax.plot([col_x+0.03, col_x+0.03], [0, rows - 1], color='black', lw=1.2)
            elif val_yp: 
                ax.text(col_x, rows - 1.5, val_yp, ha='center', va='center', fontsize=15)
                
        if not is_xet_dau and i < len(y_val_data) and y_val_data[i]:
            val_y = str(y_val_data[i]).strip()
            
            if "||" in val_y:
                parts = val_y.split("||")
                if len(parts) == 2:
                    p1, p2 = parts[0].strip(), parts[1].strip()
                    pos1 = 0.15 if left_sign == "-" else 0.85
                    pos2 = 0.85 if right_sign == "-" else 0.15
                    ax.text(col_x - 0.25, pos1, p1, ha='right', va='center', fontsize=14)
                    ax.text(col_x + 0.25, pos2, p2, ha='left', va='center', fontsize=14)
                    y_coords.append((col_x - 0.25, pos1))
                    y_coords.append((col_x + 0.25, pos2))
                    continue

            if left_sign == "+" or right_sign == "-": pos = 0.85
            elif left_sign == "-" or right_sign == "+": pos = 0.15
            else: pos = 0.5
            
            if i == 0: pos = 0.15 if right_sign == "+" else 0.85
            if i == n - 1: pos = 0.85 if left_sign == "+" else 0.15

            y_coords.append((col_x, pos))
            ax.text(col_x, pos, val_y, ha='center', va='center', fontsize=15)
    
    if not is_xet_dau:
        for i in range(len(y_coords)-1):
            x1, y1 = y_coords[i]
            x2, y2 = y_coords[i+1]
            if abs(x2 - x1) < 0.6: continue
            
            dx, dy = x2 - x1, y2 - y1
            sign_y = 1 if dy > 0 else (-1 if dy < 0 else 0.01)
            ax.annotate("", xy=(x2 - 0.2, y2 - 0.2 * sign_y), 
                        xytext=(x1 + 0.2, y1 + 0.2 * sign_y),
                        arrowprops=dict(arrowstyle="->", color="black", lw=1.5))
                        
    ax.set_xlim(0, n+1)
    ax.set_ylim(0, rows)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, transparent=True)
    buf.seek(0)
    plt.close(fig)
    return buf

# 3. HÀM TẠO POWERPOINT (ĐÃ NÂNG CẤP TÁCH TEXTBOX)
def xuat_powerpoint(noi_dung_bai_hoc, file_ra="GiaoAn_Output.pptx"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Slide Tiêu đề
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
        
        # Tiêu đề Slide
        t_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.8))
        p_t = t_box.text_frame.paragraphs[0]
        p_t.text = str(item.get("tieu_de_slide", ""))
        p_t.font.size = Pt(28)
        p_t.font.bold = True
        p_t.font.color.rgb = RGBColor(0, 51, 102)

        # Trạng thái kiểm tra có hình ảnh hay không để ép khoảng cách dòng
        has_graphic = "bang_bien_thien" in item or "bang_xet_dau" in item or "do_thi" in item
        
        # Tọa độ Y bắt đầu cho câu đầu tiên
        top_pos = Inches(1.2) 
        # Nếu có hình, các dòng chữ phải xếp khít lại để nhường không gian phía dưới
        khoang_cach_dong = Inches(0.45) if has_graphic else Inches(0.6)
        
        # TÁCH ĐỘC LẬP TỪNG TEXTBOX
        for bullet in item.get("noi_dung", []):
            # Mỗi câu là một shape mới
            c_box = slide.shapes.add_textbox(Inches(0.8), top_pos, Inches(11.7), Inches(0.5))
            tf_c = c_box.text_frame
            tf_c.word_wrap = True
            
            p_c = tf_c.paragraphs[0]
            p_c.text = f"• {bullet}"
            p_c.font.size = Pt(20)
            p_c.font.color.rgb = RGBColor(50, 50, 50)
            
            # Cốt lõi: Cộng dồn tọa độ Y để đẩy câu tiếp theo xuống dưới
            top_pos += khoang_cach_dong

        # Chèn Đồ thị
        if "do_thi" in item:
            dt = item["do_thi"]
            buf = tao_anh_do_thi(dt.get("bieu_thuc", "x"), dt.get("x_min", -5), dt.get("x_max", 5))
            if buf:
                slide.shapes.add_picture(buf, Inches(3.5), Inches(3.8), width=Inches(5.5))
                
        # Chèn Bảng biến thiên
        elif "bang_bien_thien" in item:
            buf = tao_anh_bbt(item["bang_bien_thien"], is_xet_dau=False)
            if buf:
                slide.shapes.add_picture(buf, Inches(2.1), Inches(4.0), width=Inches(9))
                
        # Chèn Bảng xét dấu
        elif "bang_xet_dau" in item:
            buf = tao_anh_bbt(item["bang_xet_dau"], is_xet_dau=True)
            if buf:
                slide.shapes.add_picture(buf, Inches(2.5), Inches(4.5), width=Inches(8))

    prs.save(file_ra)
    return file_ra

# 4. HÀM GỌI AI PHÂN TÍCH TÀI LIỆU
def phan_tich_tai_lieu_ai(file_tai_len, ai_model):
    file_bytes = file_tai_len.getvalue()
    ten_file = file_tai_len.name.lower()

    prompt = """
    Bạn là chuyên gia sư phạm Toán học. Đọc tài liệu và biên soạn giáo án PowerPoint.
    
    CẢNH BÁO: Dịch toàn bộ mã LaTeX sang Unicode (VD: x₁, x², ∞, ∈, ℝ, phân số a/b). TUYỆT ĐỐI không để lại dấu \\.
    
    YÊU CẦU ĐỒ HỌA TRỰC QUAN (BẮT BUỘC ĐỐI VỚI BÀI HÀM SỐ):
    Hễ tài liệu nhắc đến hàm số cụ thể, bạn BẮT BUỘC phải chèn 1 trong 3 đối tượng sau vào JSON của slide đó:
    1. "bang_xet_dau": Gồm 2 mảng "x" và "y_phay" (Dùng khi xét dấu đạo hàm).
    2. "bang_bien_thien": Gồm 3 mảng "x", "y_phay", "y_val" (Dùng khi tìm cực trị/đơn điệu).
    3. "do_thi": Vẽ đồ thị. Cung cấp "bieu_thuc" (phải dùng cú pháp Python như x**3 - 3*x**2), "x_min", "x_max".
    
    ĐỊNH DẠNG ĐẦU RA JSON:
    {
        "tieu_de": "Tên bài học",
        "mon": "Toán học",
        "giao_vien": "Hồ Thuyết Dũng",
        "cac_slide": [
            {
                "tieu_de_slide": "Ví dụ Đồ thị",
                "noi_dung": ["Quan sát đồ thị hàm số y = x³ - 3x:"],
                "do_thi": {"bieu_thuc": "x**3 - 3*x", "x_min": -3, "x_max": 3}
            },
            {
                "tieu_de_slide": "Bảng xét dấu",
                "noi_dung": ["Ta có bảng xét dấu đạo hàm:"],
                "bang_xet_dau": {
                    "x": ["-∞", "", "1", "", "+∞"],
                    "y_phay": ["", "+", "0", "-", ""]
                }
            },
            {
                "tieu_de_slide": "Bảng biến thiên",
                "noi_dung": ["Bảng biến thiên hoàn chỉnh:"],
                "bang_bien_thien": {
                    "x": ["-∞", "", "1", "", "3", "", "+∞"],
                    "y_phay": ["", "+", "0", "-", "0", "+", ""],
                    "y_val": ["-∞", "", "4", "", "0", "", "+∞"]
                }
            }
        ]
    }
    LƯU Ý: Phải xuất tối thiểu 15 slide. Đừng gộp các ví dụ lại với nhau. Trả về JSON thuần.
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
    
    # Sửa lỗi Regex hoàn toàn nằm trên 1 dòng duy nhất
    raw_json = re.sub(r'```(?:json)?', '', raw_json).strip()
    raw_json = re.sub(r'```', '', raw_json).strip()
    
    try:
        match = re.search(r'\{.*\}', raw_json, re.DOTALL)
        if match:
            clean_json = match.group(0)
            clean_json = clean_json.replace('\\', '\\\\')
            return json.loads(clean_json, strict=False)
        else:
            raise ValueError("Không tìm thấy cấu trúc JSON")
    except Exception as e:
        fixed_json = raw_json.replace('\\', '\\\\')
        return json.loads(fixed_json, strict=False)

# GIAO DIỆN CHÍNH
st.write("Chọn tài liệu bài giảng nguồn (PDF, Word hoặc TXT) để tự động soạn Slide:")
file_tai_len = st.file_uploader("Tải tài liệu lên", type=["pdf", "docx", "txt"], label_visibility="collapsed")

if file_tai_len and selected_model:
    if st.button("🚀 Bắt đầu soạn giáo án tự động"):
        with st.spinner(f"AI ({selected_model}) đang thiết kế giáo án và vẽ đồ họa..."):
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

LESSONSTUDIO V8.3 — MATH VISUAL FIRST

MỤC TIÊU
Biến đồ thị, bảng biến thiên và hình Toán học thành thành phần bắt buộc của bài giảng khi nội dung yêu cầu học sinh quan sát hoặc khai thác hình.

NÂNG CẤP CHÍNH
1. Visual Contract tự phát hiện các cụm “đồ thị”, “quan sát hình”, “Hình 1.x”, “bảng biến thiên”, “bảng xét dấu”.
2. Thiếu visual bắt buộc sinh lỗi FAIL: MISSING_REQUIRED_VISUAL, MISSING_GRAPH_OR_IMAGE hoặc MISSING_VARIATION_TABLE.
3. Layout visual nhưng không có dữ liệu hình cũng bị chặn.
4. Density Budget phát hiện slide có quá nhiều chữ, quá nhiều bullet hoặc quá nhiều khối cạnh tranh không gian.
5. Slide quá tải được tách theo nguyên tắc bảo toàn nội dung trước khi dựng PowerPoint.
6. Công thức chỉ đặt trong vùng an toàn, tối đa hai công thức trong một khối.
7. Nhiệm vụ và sản phẩm có vùng riêng; không dùng AutoFit để thu chữ xuống mức khó đọc.
8. Đáp án/gợi ý được chuyển sang slide riêng, không còn chồng lên nhiệm vụ và công thức.
9. Prompt AI quy định đồ họa Toán học là bắt buộc khi hoạt động học tập cần quan sát.
10. Báo cáo QA mang phiên bản 8.3.0 và khóa xuất khi thiếu visual hoặc có nguy cơ tràn/chồng.

QUY TẮC PHÁT HÀNH
- Chỉ PASS khi mọi tham chiếu trực quan có tài sản tương ứng.
- Bảng biến thiên có dữ liệu nhưng kiểm chứng sai vẫn là FAIL.
- Không tự bịa hình hoặc bảng khi thiếu dữ liệu toán học; yêu cầu AI tạo lại hoặc giáo viên bổ sung.
- AUTO QA không thay thế việc duyệt chuyên môn của giáo viên.

CÁCH CHẠY
pip install -r requirements.txt
streamlit run app.py

KIỂM THỬ
python -m unittest discover -s tests -v

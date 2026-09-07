LESSON STUDIO V7.2 P0 SAFETY RELEASE

Các lỗi P0 đã xử lý:
1. Chuẩn hóa toàn bộ tên tệp Python để chạy trực tiếp trên GitHub/Streamlit.
2. Tạo dấu vân tay riêng cho toàn đề, không dùng nhầm fingerprint của một câu hỏi.
3. Thêm Safe Math Parser dựa trên AST và danh sách cho phép; không sympify trực tiếp chuỗi không tin cậy.
4. Siết kiểm tra bảng biến thiên: tập xác định, điểm tới hạn, điểm gián đoạn, dấu đạo hàm và giá trị/giới hạn.
5. Đồng bộ answer_index, check.correct_index và đáp án chữ cái khi đảo phương án.
6. Bổ sung kiểm thử tự động trong thư mục tests.
7. Đổi nhãn CERTIFIED thành AUTO_QA_PASSED để không gây hiểu nhầm là đã được chuyên gia duyệt.

CÁCH CHẠY KIỂM THỬ
python -m unittest discover -s tests -v

CÁCH CHẠY ỨNG DỤNG
pip install -r requirements.txt
streamlit run app.py

LƯU Ý
- Chỉ dùng dấu * cho phép nhân trong các trường expression, ví dụ 2*x thay vì 2x.
- AUTO_QA_PASSED chỉ có nghĩa là không phát hiện lỗi trong phạm vi kiểm tra tự động.
- Giáo viên vẫn phải duyệt chuyên môn trước khi sử dụng hoặc phát hành.

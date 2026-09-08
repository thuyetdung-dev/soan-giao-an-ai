LESSONSTUDIO V8.4 — VISUAL RECOVERY & TEACHER ASSET HUB

TÍNH NĂNG MỚI
1. Tự nhận diện biểu thức f(x)=... hoặc y=... trong slide thiếu visual.
2. Tự tạo cấu hình đồ thị khi biểu thức qua Safe Math Parser.
3. Tự dựng bảng biến thiên cho hàm có hữu hạn điểm tới hạn và cấu trúc đủ an toàn.
4. Không tự dựng khi thiếu dữ kiện, có điểm gián đoạn cần giới hạn một phía hoặc không chứng minh được dấu.
5. Danh sách WAITING_FOR_TEACHER_ASSET chỉ rõ slide cần giáo viên xử lý.
6. Giáo viên có thể nhập biểu thức để dựng visual, tải PNG/JPG/WEBP hoặc chọn ảnh trích từ DOCX nguồn.
7. Ảnh được kiểm tra định dạng, giới hạn 12 MB, mã hóa trong checkpoint và chèn trực tiếp vào PPTX.
8. Visual tự dựng phải được giáo viên duyệt trước khi QA mở khóa.
9. Mọi thay đổi visual làm mất trạng thái duyệt storyboard, buộc kiểm tra lại trước khi phát hành.
10. Renderer ưu tiên ảnh giáo viên/ảnh nguồn, sau đó mới dùng đồ thị tự dựng.

QUY TRÌNH
Visual QA → Tự phục hồi → Giáo viên duyệt; nếu không đủ dữ kiện → Teacher Asset Hub → Render lại → QA → Xuất PPTX.

CÀI ĐẶT
pip install -r requirements.txt
streamlit run app.py

KIỂM THỬ
python -m unittest discover -s tests -v

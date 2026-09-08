LESSONSTUDIO V9.0 — VISUAL SPECIFICATION POWERPOINT

MỤC TIÊU
- Nhập trực tiếp checkpoint bài giảng hoặc JSON ngân hàng câu hỏi mcq/tf/sa.
- Tách data-mathviz khỏi câu hỏi thành Visual Specification độc lập.
- Dựng đồ thị, bảng biến thiên, bảng xét dấu và hình triển khai hộp không nắp.
- Chặn xuất khi câu tham chiếu hình nhưng chưa có visual; cho phép giáo viên bổ sung ảnh tại Teacher Asset Hub.
- Dùng vùng chữ và vùng hình độc lập để chống chữ/khung chồng lên nhau.

CÁCH DÙNG NHANH
1. Mở ứng dụng và chọn Tạo bài giảng PowerPoint.
2. Tại mục 2, tải JSON bài giảng hoặc JSON ngân hàng câu hỏi.
3. Bấm “NHẬP JSON VÀ DỰNG BÀI GIẢNG”.
4. Xem cảnh báo Visual Contract. Nếu thiếu hình, chọn slide và tải ảnh giáo viên cung cấp.
5. Duyệt storyboard, báo cáo QA và xuất PowerPoint.

SCHEMA VISUALS KHUYẾN NGHỊ
"visuals":[{"type":"dothi|bbt|xetdau|net","placement":"below_question","payload":{...}}]

TƯƠNG THÍCH
- Vẫn nhận graph, variation_table và image_asset của V8.3–V8.5.
- Vẫn nhận data-mathviz nhúng trong q của JSON ngân hàng câu hỏi.
- Các loại hình chưa có schema chính xác phải dùng Teacher Asset Hub, không tự bịa hình.

KIỂM THỬ
- python -m py_compile *.py tests/*.py
- python -m unittest tests.test_mathviz_v9 -v

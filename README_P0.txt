LESSON STUDIO V8.2 — MULTI-SOURCE & CHECKPOINT REVIEW

NÂNG CẤP V8.2
1. Cho phép chọn đồng thời tối đa 8 tệp nguồn PDF, DOCX, TXT hoặc JSON; tổng dung lượng tối đa 50 MB.
2. Tài liệu văn bản được ghép có nhãn tên nguồn; mỗi PDF được gửi như một phần nguồn riêng.
3. Danh mục nguồn được chuyển cho AI theo đúng thứ tự và source_ref phải ghi tên tệp thực tế đã sử dụng.
4. Sau mỗi chặng, dựng ngay PowerPoint xem trước từ slide 1 đến slide hiện tại.
5. Cho tải thêm JSON checkpoint để bảo toàn cấu trúc đã tạo.
6. Nút tạo chặng tiếp theo bị khóa cho đến khi giáo viên xác nhận đã xem và duyệt chặng hiện tại.
7. Giáo viên có thể dừng ngay khi phát hiện sai, không phải chờ toàn bộ bài hoàn thành.

NỀN TẢNG V8.1
1. Không còn buộc AI tạo toàn bộ 40–50 slide trong một lượt.
2. Lần đầu lập bản đồ slide_plan cho toàn bài và chỉ tạo tối đa 10 slide đầu.
3. Hiển thị nút tiếp nối theo đúng phạm vi: 1–10, 11–20, 21–30, 31–40; chặng cuối tự rút gọn nếu tổng không chia hết cho 10.
4. Mỗi chặng sau nhận nhật ký tiêu đề, hoạt động, ba ý kiến thức và công thức của toàn bộ slide đã tạo.
5. Khóa chống lặp trong prompt và kiểm tra độ tương đồng trước khi ghép; chặng bị lặp sẽ không được nhập vào bài.
6. Ghép theo đúng thứ tự và chỉ chạy QA toàn bài khi đã đủ số slide giáo viên yêu cầu.
7. Có thanh tiến độ, bảng danh sách slide đã tạo và nút bắt đầu lại rõ ràng.
8. Hồ sơ bài học và Storyboard toàn bài được lập ở chặng đầu để các chặng sau không làm lệch tiến trình CTGDPT 2018.

NỀN TẢNG V8.0.2
1. Kiểm định ngay sau lượt sinh đầu để phát hiện thiếu slide và thiếu một trong 5 pha hoạt động.
2. Nếu lệch quá 2 slide hoặc thiếu pha, chạy tối đa một lượt hoàn thiện cấu trúc có khóa nguồn.
3. Lượt hoàn thiện phải giữ đúng bài học, không thêm kiến thức mới, đủ 5 pha và đúng tổng thời gian 45 phút/tiết.
4. Chỉ nhận bản hoàn thiện nếu kết quả QA tốt hơn bản đầu theo thứ tự: ít lỗi FAIL hơn, gần số slide yêu cầu hơn, ít cảnh báo REVIEW hơn.
5. Nếu lượt hoàn thiện hết quota hoặc JSON lỗi, giữ nguyên bản đầu; không làm mất kết quả đã tạo.
6. Không sao chép lặp nội dung chỉ để đủ số slide.

NỀN TẢNG AI FALLBACK V8.0.1
1. Nhận diện riêng lỗi 429/quota, lỗi máy chủ tạm thời và lỗi API Key/quyền truy cập.
2. Nếu hạn mức theo ngày của mô hình đang chọn đã hết, tự chuyển sang mô hình Gemini dự phòng đang có trong tài khoản.
3. Nếu lỗi tạm thời có retry_delay, chỉ chờ và thử lại một lần theo thời gian Google chỉ định (tối đa 35 giây), tránh vòng lặp vô hạn.
4. Hiển thị tiến trình chuyển mô hình bằng tiếng Việt và cho biết mô hình thực tế đã tạo bài.
5. Nếu mọi mô hình đều hết hạn mức, dừng an toàn, giữ nguyên biểu mẫu và tệp đã tải trong phiên làm việc.
6. Không chia một yêu cầu bị lỗi quota thành nhiều yêu cầu nhỏ vì cách đó làm tiêu tốn thêm số lượt API; bài dài vẫn được sinh trong một lượt rồi kiểm định như V8.0.

NÂNG CẤP NỀN TẢNG V8.0
1. Sinh Hồ sơ bài học có cấu trúc: vị trí bài, phạm vi nguồn, kiến thức tiền đề, yêu cầu cần đạt, kiến thức cốt lõi, sai lầm thường gặp, nội dung ngoài phạm vi và thiết bị/học liệu.
2. Mỗi yêu cầu cần đạt gắn với mức độ nhận thức, năng lực toán học, minh chứng học tập và cách đánh giá.
3. Sinh Storyboard đủ 5 pha: Khởi động, Hình thành kiến thức, Luyện tập, Vận dụng, Củng cố.
4. Mỗi hoạt động có thời lượng, mục tiêu, cách tổ chức, việc học sinh làm, sản phẩm, đánh giá, câu hỏi gợi mở, khó khăn dự kiến, hỗ trợ/phân hóa và kết luận.
5. Kiểm tra tổng thời gian theo 45 phút/tiết và kiểm tra liên kết hoạt động với slide.
6. Tách ba khu vực duyệt: Hồ sơ bài học, Storyboard CTGDPT 2018 và báo cáo QA.
7. Chỉ mở khóa tải PowerPoint sau khi không còn lỗi FAIL và giáo viên xác nhận đã duyệt hồ sơ/storyboard.
8. PowerPoint có thêm các trang kế hoạch giáo viên cho Hồ sơ bài học và Storyboard; giáo viên có thể ẩn các trang này trước khi trình chiếu cho học sinh.
9. Báo cáo QA tải về chứa đồng thời kiểm định slide và kiểm định CTGDPT 2018.

NỀN TẢNG AN TOÀN P0/P0.1 ĐƯỢC GIỮ NGUYÊN

Các lỗi P0 đã xử lý:
1. Chuẩn hóa toàn bộ tên tệp Python để chạy trực tiếp trên GitHub/Streamlit.
2. Tạo dấu vân tay riêng cho toàn đề, không dùng nhầm fingerprint của một câu hỏi.
3. Thêm Safe Math Parser dựa trên AST và danh sách cho phép; không sympify trực tiếp chuỗi không tin cậy.
4. Siết kiểm tra bảng biến thiên: tập xác định, điểm tới hạn, điểm gián đoạn, dấu đạo hàm và giá trị/giới hạn.
5. Đồng bộ answer_index, check.correct_index và đáp án chữ cái khi đảo phương án.
6. Bổ sung kiểm thử tự động trong thư mục tests.
7. Đổi nhãn CERTIFIED thành AUTO_QA_PASSED để không gây hiểu nhầm là đã được chuyên gia duyệt.
8. Có nút TỰ SỬA AN TOÀN VÀ KIỂM ĐỊNH LẠI.
9. Bảng biến thiên không kiểm chứng được sẽ bị ẩn khỏi PowerPoint, có ghi dấu trong Notes và báo REVIEW.
10. Chuẩn hóa các lệnh LaTeX phổ biến trong textbox thành ký hiệu Unicode dễ đọc.

CÁCH CHẠY KIỂM THỬ
python -m unittest discover -s tests -v

CÁCH CHẠY ỨNG DỤNG
pip install -r requirements.txt
streamlit run app.py

LƯU Ý
- Chỉ dùng dấu * cho phép nhân trong các trường expression, ví dụ 2*x thay vì 2x.
- AUTO_QA_PASSED chỉ có nghĩa là không phát hiện lỗi trong phạm vi kiểm tra tự động.
- Giáo viên vẫn phải duyệt chuyên môn trước khi sử dụng hoặc phát hành.

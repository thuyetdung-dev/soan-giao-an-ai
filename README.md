# LessonStudio V10 — Next.js/Vercel

Bản viết lại từ LessonStudio V9.0 Streamlit, ưu tiên hiển thị Toán học ổn định.

## Chạy cục bộ

1. Sao chép `.env.example` thành `.env.local` và nhập `GEMINI_API_KEY`.
2. Chạy `npm install`.
3. Chạy `npm run dev`.

## Triển khai Vercel

Import repository vào Vercel, thêm biến môi trường `GEMINI_API_KEY` và Deploy. Không đặt khóa API trong mã nguồn hay biến `NEXT_PUBLIC_*`.

## Visual Specification

Các hình Toán không được AI xuất thành ảnh. AI chỉ sinh JSON có cấu trúc; ứng dụng tự dựng `formula`, `variation_table`, `sign_chart` và `graph`. Điều này giúp hình nhất quán, có thể kiểm tra và sửa dữ liệu độc lập.

import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";
import "./key-panel.css";
import "./bbt.css";
import "./features.css";
import "./reference.css";
import "./v9-layout.css";
export const metadata: Metadata={title:"Trợ lý soạn PowerPoint Toán THPT",description:"LessonStudio V10 tạo PowerPoint bài giảng Toán với bảng biến thiên, bảng xét dấu và đồ thị"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="vi"><body>{children}</body></html>}

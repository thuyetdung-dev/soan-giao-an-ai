import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";
import "./key-panel.css";
import "./bbt.css";
import "./features.css";
import "./reference.css";
import "./v9-layout.css";
export const metadata: Metadata={title:"LessonStudio V10",description:"Soạn bài giảng Toán với Visual Specification chính xác"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="vi"><body>{children}</body></html>}

import {NextResponse} from "next/server";
const SYSTEM=`Bạn là engine LessonStudio V10 cho Toán THPT. Chỉ trả JSON hợp lệ: {"title":string,"subject":"Toán","grade":string,"sections":[{"heading":string,"content":string,"visuals":Visual[]}]}.
Visual chỉ thuộc một trong bốn dạng:
1 {"type":"formula","latex":string,"display":true}
2 {"type":"variation_table","x":string[],"derivative":string[],"values":string[]}
3 {"type":"sign_chart","label":string,"x":string[],"signs":string[]}
4 {"type":"graph","expression":string dùng cú pháp JS an toàn chỉ gồm x,số,+,-,*,/,^,ngoặc,"xMin":number,"xMax":number,"yMin":number,"yMax":number,"points":[]}
Không dùng Markdown fence. Mọi hình phải có dữ liệu số học xác định; không bịa ảnh.`;
export async function POST(req:Request){try{const key=process.env.GEMINI_API_KEY;if(!key)return NextResponse.json({error:"Chưa cấu hình GEMINI_API_KEY trên Vercel."},{status:503});const {prompt}=await req.json();const model=process.env.GEMINI_MODEL||"gemini-2.5-flash";const r=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,{method:"POST",headers:{"content-type":"application/json","x-goog-api-key":key},body:JSON.stringify({systemInstruction:{parts:[{text:SYSTEM}]},contents:[{role:"user",parts:[{text:String(prompt||"")}]}],generationConfig:{responseMimeType:"application/json",temperature:.25}})});const raw=await r.json();if(!r.ok)throw new Error(raw?.error?.message||"Gemini API lỗi");const text=raw?.candidates?.[0]?.content?.parts?.[0]?.text;const data=JSON.parse(text);return NextResponse.json(data)}catch(e){return NextResponse.json({error:e instanceof Error?e.message:"Dữ liệu AI không hợp lệ"},{status:500})}}

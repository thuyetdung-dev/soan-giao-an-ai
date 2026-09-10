import type {Lesson,Visual} from "./types";

function safeName(s:string){return s.normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-zA-Z0-9]+/g,"_").slice(0,70)}
async function loadPptx(){const w=window as unknown as {PptxGenJS?:new()=>any};if(w.PptxGenJS)return w.PptxGenJS;await new Promise<void>((resolve,reject)=>{const s=document.createElement("script");s.src="https://cdn.jsdelivr.net/npm/pptxgenjs@4.0.1/dist/pptxgen.bundle.js";s.onload=()=>resolve();s.onerror=()=>reject(new Error("Không tải được bộ xuất PowerPoint"));document.head.appendChild(s)});if(!w.PptxGenJS)throw new Error("Bộ xuất PowerPoint chưa sẵn sàng");return w.PptxGenJS}

const C={navy:"17324D",coral:"FF5A5F",ink:"17283A",muted:"6D7B8A",white:"FFFFFF",line:"D9E3EA",green:"159A80"};
function addChrome(slide:any,index:number,title:string){slide.background={color:C.white};slide.addShape("rect",{x:0,y:0,w:13.333,h:.12,line:{color:C.navy,transparency:100},fill:{color:C.navy}});slide.addShape("rect",{x:.58,y:.55,w:.12,h:.58,line:{color:C.coral,transparency:100},fill:{color:C.coral}});slide.addText(title,{x:.86,y:.48,w:11.2,h:.6,fontFace:"Aptos Display",fontSize:26,bold:true,color:C.navy,margin:0,fit:"shrink"});slide.addText(String(index).padStart(2,"0"),{x:12.1,y:.55,w:.55,h:.28,fontFace:"Aptos",fontSize:10,bold:true,color:C.muted,align:"right",margin:0});slide.addShape("line",{x:.58,y:1.18,w:12.15,h:0,line:{color:C.line,width:1}})}
function visualName(v:Visual){return v.type==="variation_table"?"Bảng biến thiên":v.type==="sign_chart"?"Bảng xét dấu":v.type==="graph"?"Đồ thị hàm số":"Công thức trọng tâm"}
function addFooter(slide:any,lesson:Lesson){slide.addText(`${lesson.subject||"Toán"} · Lớp ${lesson.grade||"THPT"}`,{x:.62,y:7.15,w:5,h:.2,fontFace:"Aptos",fontSize:9,color:"8493A1",margin:0});slide.addText("LessonStudio V10",{x:10.7,y:7.15,w:2,h:.2,fontFace:"Aptos",fontSize:9,color:"8493A1",align:"right",margin:0})}
function cleanText(s:string){return String(s||"").replace(/\s+/g," ").trim()}

export async function exportPptx(root:HTMLElement,lesson:Lesson,meta?:{teacher?:string;school?:string}){
 const [PptxGenJS,{default:html2canvas}]=await Promise.all([loadPptx(),import("html2canvas")]);
 const pptx=new PptxGenJS();pptx.layout="LAYOUT_WIDE";pptx.author=meta?.teacher||"LessonStudio V10";pptx.subject="Bài giảng PowerPoint Toán THPT";pptx.title=lesson.title;pptx.company=meta?.school||"";pptx.lang="vi-VN";pptx.theme={headFontFace:"Aptos Display",bodyFontFace:"Aptos",lang:"vi-VN"};
 const cover=pptx.addSlide();cover.background={color:C.navy};cover.addShape("rect",{x:.72,y:.72,w:.18,h:5.9,line:{transparency:100},fill:{color:C.coral}});cover.addText("BÀI GIẢNG TOÁN THPT",{x:1.25,y:1.05,w:6.7,h:.35,fontFace:"Aptos",fontSize:14,bold:true,charSpacing:2.2,color:"8FD6F0",margin:0});cover.addText(lesson.title,{x:1.25,y:1.65,w:10.5,h:1.55,fontFace:"Aptos Display",fontSize:34,bold:true,color:C.white,margin:0,fit:"shrink",valign:"mid"});cover.addShape("line",{x:1.25,y:3.55,w:2.2,h:0,line:{color:C.coral,width:4}});cover.addText(`${lesson.subject||"Toán"}  |  Lớp ${lesson.grade||"THPT"}`,{x:1.25,y:3.92,w:7,h:.42,fontFace:"Aptos",fontSize:18,color:"C8D7E3",margin:0});if(meta?.teacher)cover.addText(`Giáo viên: ${meta.teacher}`,{x:1.25,y:4.55,w:7,h:.36,fontFace:"Aptos",fontSize:15,color:C.white,margin:0});if(meta?.school)cover.addText(meta.school,{x:1.25,y:5.05,w:8,h:.32,fontFace:"Aptos",fontSize:13,color:"A9BAC8",margin:0});cover.addText("V10",{x:10.5,y:5.45,w:1.5,h:.8,fontFace:"Aptos Display",fontSize:34,bold:true,color:C.coral,align:"right",margin:0});
 const articles=[...root.querySelectorAll("article")];let slideNo=1;
 for(let si=0;si<lesson.sections.length;si++){
   const section=lesson.sections[si],text=cleanText(section.content),visuals=section.visuals||[];
   const slide=pptx.addSlide();addChrome(slide,slideNo++,section.heading);addFooter(slide,lesson);slide.addText(String(si+1).padStart(2,"0"),{x:.78,y:1.72,w:1.15,h:.78,fontFace:"Aptos Display",fontSize:36,bold:true,color:C.coral,margin:0});slide.addText(text,{x:2.05,y:1.62,w:10.15,h:4.72,fontFace:"Aptos",fontSize:21,color:C.ink,fit:"shrink",valign:"top",margin:.08,paraSpaceAfterPt:12});if(visuals.length)slide.addText(`${visuals.length} hình Toán kèm theo`,{x:2.05,y:6.38,w:4,h:.3,fontFace:"Aptos",fontSize:11,bold:true,color:C.green,margin:0});
   const visualNodes=[...(articles[si]?.querySelectorAll(".visual-card")||[])];
   for(let vi=0;vi<visuals.length;vi++){
     const v=visuals[vi],node=visualNodes[vi] as HTMLElement|undefined,vs=pptx.addSlide();addChrome(vs,slideNo++,`${section.heading} · ${visualName(v)}`);addFooter(vs,lesson);
     if(node){const canvas=await html2canvas(node,{scale:2.35,backgroundColor:"#ffffff",useCORS:true,logging:false});const ratio=canvas.width/canvas.height,maxW=11.7,maxH=5.45;let w=maxW,h=w/ratio;if(h>maxH){h=maxH;w=h*ratio}vs.addImage({data:canvas.toDataURL("image/png"),x:(13.333-w)/2,y:1.48+(maxH-h)/2,w,h});}else vs.addText("Không dựng được hình Toán",{x:1,y:3,w:11.3,h:.5,fontSize:22,color:C.coral,align:"center"});
   }
 }
 await pptx.writeFile({fileName:`${safeName(lesson.title)}_BAI_GIANG.pptx`});
}

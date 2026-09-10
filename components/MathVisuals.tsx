"use client";
import katex from "katex";
import type {GraphVisual,SignVisual,VariationVisual,Visual} from "@/lib/types";

const MathText=({value,display=false}:{value:string;display?:boolean})=><span className={display?"math display":"math"} dangerouslySetInnerHTML={{__html:katex.renderToString(value,{throwOnError:false,displayMode:display,strict:"ignore"})}}/>;

function plainMath(s:string){return String(s??"").replace(/\\infty/g,"∞").replace(/\\pm/g,"±").replace(/\\/g,"").replace(/[{}]/g,"")}
function valueRank(s:string){const t=plainMath(s).replace(/\s/g,"");if(t.includes("+∞")||t==="∞")return 1;if(t.includes("-∞"))return 0;const n=Number(t);return Number.isFinite(n)?0.2+0.6/(1+Math.exp(-n/3)):0.5}
function VariationTable({v}:{v:VariationVisual}){
 const W=760,H=265,L=76,top=12,xRow=54,dRow=102,bottom=250,n=Math.max(2,v.x.length),step=(W-L)/(n-1),xs=Array.from({length:n},(_,i)=>L+i*step),dis=new Map((v.discontinuities||[]).map(d=>[d.index,d]));
 const yOf=(s:string)=>bottom-20-valueRank(s)*(bottom-dRow-42);
 const vals=Array.from({length:n},(_,i)=>v.values[i]??"");
 const intervalSign=(i:number)=>v.derivative.length>=2*n-3?v.derivative[i*2]:v.derivative[i]??"";
 return <svg className="variation-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Bảng biến thiên">
  <defs><marker id="bbtArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#263746"/></marker></defs>
  <rect x="1" y="1" width={W-2} height={H-2} fill="#fff" stroke="#263746" strokeWidth="1.5"/><line x1={L} x2={L} y1="1" y2={H-1} stroke="#263746" strokeWidth="1.5"/><line x1="1" x2={W-1} y1={xRow} y2={xRow} stroke="#263746"/><line x1="1" x2={W-1} y1={dRow} y2={dRow} stroke="#263746"/>
  <text x={L/2} y="34" className="bbt-label">x</text><text x={L/2} y="84" className="bbt-label">y′</text><text x={L/2} y="188" className="bbt-label">y</text>
  {xs.map((x,i)=><text key={`x${i}`} x={x} y="34" className="bbt-text">{plainMath(v.x[i]??"")}</text>)}
  {Array.from({length:n-1},(_,i)=><text key={`s${i}`} x={(xs[i]+xs[i+1])/2} y="84" className="bbt-sign">{plainMath(intervalSign(i))}</text>)}
  {Array.from({length:Math.max(0,n-2)},(_,i)=><text key={`z${i}`} x={xs[i+1]} y="84" className="bbt-text">{plainMath(v.derivative[i*2+1]??"0")}</text>)}
  {Array.from({length:n-1},(_,i)=>{const a=dis.get(i),b=dis.get(i+1);if(a||b)return null;return <line key={`a${i}`} x1={xs[i]+18} y1={yOf(vals[i])} x2={xs[i+1]-18} y2={yOf(vals[i+1])} stroke="#263746" strokeWidth="2.5" markerEnd="url(#bbtArrow)"/>})}
  {vals.map((value,i)=>dis.has(i)?null:<text key={`v${i}`} x={xs[i]} y={yOf(value)-8} className="bbt-value">{plainMath(value)}</text>)}
  {[...dis.entries()].map(([i,d])=><g key={`d${i}`}><line x1={xs[i]-4} x2={xs[i]-4} y1={xRow} y2={H-1} stroke="#263746"/><line x1={xs[i]+4} x2={xs[i]+4} y1={xRow} y2={H-1} stroke="#263746"/><text x={xs[i]-13} y={yOf(d.leftValue)-8} textAnchor="end" className="bbt-value">{plainMath(d.leftValue)}</text><text x={xs[i]+13} y={yOf(d.rightValue)-8} textAnchor="start" className="bbt-value">{plainMath(d.rightValue)}</text></g>)}
 </svg>
}
function SignChart({v}:{v:SignVisual}){return <div className="math-table sign"><div className="row"><b>x</b>{v.x.map((x,i)=><MathText key={i} value={x}/>)}</div><div className="row"><b>{v.label||"f(x)"}</b>{v.signs.map((x,i)=><MathText key={i} value={x}/>)}</div></div>}

function safeEval(expr:string,x:number){if(!/^[0-9x+\-*/^().\s]+$/i.test(expr))return NaN;try{return Number(Function("x",`"use strict";return (${expr.replaceAll("^","**")})`)(x))}catch{return NaN}}
function Graph({v}:{v:GraphVisual}){const W=640,H=360,p=34;const sx=(x:number)=>p+(x-v.xMin)*(W-2*p)/(v.xMax-v.xMin);const sy=(y:number)=>H-p-(y-v.yMin)*(H-2*p)/(v.yMax-v.yMin);let paths:string[]=[];let current="";for(let i=0;i<=700;i++){const x=v.xMin+(v.xMax-v.xMin)*i/700,y=safeEval(v.expression,x);if(!Number.isFinite(y)||y<v.yMin*4||y>v.yMax*4){if(current)paths.push(current);current="";continue}current+=(current?" L ":"M ")+`${sx(x).toFixed(2)} ${sy(y).toFixed(2)}`}if(current)paths.push(current);return <svg className="graph" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Đồ thị ${v.expression}`}><rect width={W} height={H} rx="14" fill="#fff"/><g stroke="#dbe5ee" strokeWidth="1">{Array.from({length:9},(_,i)=><line key={`h${i}`} x1={p} x2={W-p} y1={p+i*(H-2*p)/8} y2={p+i*(H-2*p)/8}/>)}{Array.from({length:13},(_,i)=><line key={`v${i}`} y1={p} y2={H-p} x1={p+i*(W-2*p)/12} x2={p+i*(W-2*p)/12}/>)}</g><g stroke="#263746" strokeWidth="1.5"><line x1={p} x2={W-p} y1={sy(0)} y2={sy(0)}/><line y1={p} y2={H-p} x1={sx(0)} x2={sx(0)}/></g>{v.asymptotes?.map((a,i)=><line key={i} stroke="#e56b6f" strokeDasharray="7 6" x1={a.kind==="vertical"?sx(a.value):p} x2={a.kind==="vertical"?sx(a.value):W-p} y1={a.kind==="horizontal"?sy(a.value):p} y2={a.kind==="horizontal"?sy(a.value):H-p}/>)}{paths.map((d,i)=><path key={i} d={d} fill="none" stroke="#087e8b" strokeWidth="3"/>)}{v.points?.map((q,i)=><g key={i}><circle cx={sx(q.x)} cy={sy(q.y)} r="5" fill="#ef8354"/><text x={sx(q.x)+8} y={sy(q.y)-8}>{q.label||`(${q.x};${q.y})`}</text></g>)}</svg>}
export function MathVisual({visual}:{visual:Visual}){if(visual.type==="formula")return <MathText value={visual.latex} display={visual.display??true}/>;if(visual.type==="variation_table")return <VariationTable v={visual}/>;if(visual.type==="sign_chart")return <SignChart v={visual}/>;return <Graph v={visual}/>}

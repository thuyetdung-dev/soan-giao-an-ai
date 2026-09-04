"""Small, dependency-free LaTeX subset to editable Office Math (OMML).

Supported: fractions, radicals, superscripts, subscripts, common Greek letters,
relations, operators and grouped expressions. Unsupported commands are kept as
readable text instead of being silently deleted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
from pptx.util import Inches
from lxml import etree


SYMBOLS = {
    "alpha":"α","beta":"β","gamma":"γ","delta":"δ","epsilon":"ε","theta":"θ","lambda":"λ","mu":"μ","pi":"π","rho":"ρ","sigma":"σ","phi":"φ","omega":"ω",
    "Gamma":"Γ","Delta":"Δ","Theta":"Θ","Lambda":"Λ","Pi":"Π","Sigma":"Σ","Phi":"Φ","Omega":"Ω",
    "infty":"∞","pm":"±","mp":"∓","times":"×","cdot":"·","div":"÷","le":"≤","leq":"≤","ge":"≥","geq":"≥","ne":"≠","neq":"≠","in":"∈","notin":"∉","subset":"⊂","subseteq":"⊆","cup":"∪","cap":"∩","to":"→","rightarrow":"→","leftarrow":"←","Leftrightarrow":"⇔","Rightarrow":"⇒","approx":"≈","equiv":"≡",
    "sin":"sin","cos":"cos","tan":"tan","cot":"cot","ln":"ln","log":"log","exp":"exp","max":"max","min":"min","lim":"lim","sum":"∑","prod":"∏","int":"∫",
    "mathbb":"", "mathrm":"", "mathbf":"", "left":"", "right":"",
}


def formula_diagnostics(text: str) -> list[str]:
    issues=[]; stack=[]; pairs={"}":"{",")":"(","]":"["}
    for char in str(text):
        if char in "{([": stack.append(char)
        elif char in "})]":
            if not stack or stack.pop()!=pairs[char]: issues.append("Ngoặc không cân bằng"); break
    if stack and "Ngoặc không cân bằng" not in issues: issues.append("Ngoặc không cân bằng")
    commands=[]; i=0; s=str(text)
    while i<len(s):
        if s[i]=="\\":
            i+=1; start=i
            while i<len(s) and s[i].isalpha(): i+=1
            if start<i: commands.append(s[start:i])
        else: i+=1
    unknown=sorted({c for c in commands if c not in SYMBOLS and c not in {"frac","sqrt","text","begin","end","begincases","endcases"}})
    if unknown: issues.append("Lệnh LaTeX chưa hỗ trợ: "+", ".join(unknown))
    return issues


@dataclass
class Node:
    kind: str
    text: str = ""
    children: list[Any] = field(default_factory=list)


class Parser:
    def __init__(self, text: str):
        value=text.strip().strip("$")
        value=value.replace(r"\begin{cases}", "{ ").replace(r"\end{cases}", "")
        value=value.replace(r"\begincases", "{ ").replace(r"\endcases", "")
        value=value.replace(r"\begin{aligned}", "").replace(r"\end{aligned}", "")
        value=value.replace(r"\\", " ; ").replace("&", "")
        self.s=value; self.i=0
    def parse(self, stop: str = "") -> list[Node]:
        out=[]; buf=""
        def flush():
            nonlocal buf
            if buf: out.append(Node("text",buf)); buf=""
        while self.i<len(self.s):
            c=self.s[self.i]
            if stop and c==stop: flush(); self.i+=1; break
            if c=="{": flush(); self.i+=1; out.extend(self.parse("}")); continue
            if c=="\\":
                flush(); self.i+=1; start=self.i
                while self.i<len(self.s) and self.s[self.i].isalpha(): self.i+=1
                cmd=self.s[start:self.i]
                if not cmd and self.i<len(self.s): out.append(Node("text",self.s[self.i])); self.i+=1; continue
                if cmd=="frac": out.append(Node("frac",children=[self.group(),self.group()])); continue
                if cmd=="sqrt": out.append(Node("sqrt",children=[self.group()])); continue
                if cmd in {"text","mathrm","mathbf","mathbb"}: out.extend(self.group()); continue
                out.append(Node("text",SYMBOLS.get(cmd,"\\"+cmd))); continue
            if c in "^_":
                flush(); self.i+=1; script=self.group(single_ok=True)
                base=out.pop() if out else Node("text","")
                if base.kind=="sub" and c=="^": out.append(Node("subsup",children=[base.children[0],base.children[1],script]))
                elif base.kind=="sup" and c=="_": out.append(Node("subsup",children=[base.children[0],script,base.children[1]]))
                else: out.append(Node("sup" if c=="^" else "sub",children=[base,script]))
                continue
            if c=="~": buf+=" "; self.i+=1; continue
            buf+=c; self.i+=1
        flush(); return out
    def group(self,single_ok=False) -> list[Node]:
        while self.i<len(self.s) and self.s[self.i].isspace(): self.i+=1
        if self.i<len(self.s) and self.s[self.i]=="{": self.i+=1; return self.parse("}")
        if single_ok and self.i<len(self.s):
            if self.s[self.i]=="\\":
                start=self.i; self.i+=1
                while self.i<len(self.s) and self.s[self.i].isalpha(): self.i+=1
                return Parser(self.s[start:self.i]).parse()
            c=self.s[self.i]; self.i+=1; return [Node("text",c)]
        return []


def _el(tag: str, attrs: dict[str,str] | None=None):
    node=OxmlElement(tag)
    for key,value in (attrs or {}).items(): node.set(qn(key) if ":" in key else key,value)
    return node


def _run(text: str, size: int, color: tuple[int,int,int]):
    r=_el("m:r"); rpr=_el("m:rPr"); rpr.append(_el("m:sty",{"m:val":"p"}))
    arpr=_el("a:rPr",{"lang":"vi-VN","sz":str(size*100),"b":"0"})
    arpr.append(_el("a:solidFill")); arpr[0].append(_el("a:srgbClr",{"val":"%02X%02X%02X"%color}))
    rpr.append(arpr); r.append(rpr); t=_el("m:t"); t.text=text; r.append(t); return r


def _container(tag: str, child_tag: str, nodes: list[Node], size: int, color):
    root=_el(tag); child=_el(child_tag)
    for node in nodes: child.append(_to_omml(node,size,color))
    root.append(child); return root


def _sequence(nodes: list[Node], size: int, color):
    return [_to_omml(node,size,color) for node in nodes]


def _to_omml(node: Node, size: int, color):
    if node.kind=="text": return _run(node.text,size,color)
    if node.kind=="frac":
        f=_el("m:f"); f.append(_el("m:fPr"))
        for tag,nodes in (("m:num",node.children[0]),("m:den",node.children[1])):
            part=_el(tag)
            for x in _sequence(nodes,size,color): part.append(x)
            f.append(part)
        return f
    if node.kind=="sqrt":
        rad=_el("m:rad"); rp=_el("m:radPr"); rp.append(_el("m:degHide",{"m:val":"1"})); rad.append(rp); rad.append(_el("m:deg")); e=_el("m:e")
        for x in _sequence(node.children[0],size,color): e.append(x)
        rad.append(e); return rad
    tags={"sup":("m:sSup",("m:e","m:sup")),"sub":("m:sSub",("m:e","m:sub")),"subsup":("m:sSubSup",("m:e","m:sub","m:sup"))}
    if node.kind in tags:
        root_tag,parts=tags[node.kind]; root=_el(root_tag); root.append(_el(root_tag+"Pr"))
        for tag,nodes in zip(parts,node.children):
            part=_el(tag)
            seq=nodes if isinstance(nodes,list) else [nodes]
            for x in _sequence(seq,max(12,size-3),color): part.append(x)
            root.append(part)
        return root
    return _run(node.text,size,color)


def append_omml(paragraph, latex: str, size: int = 24, color=(16,62,105)) -> None:
    nodes=Parser(latex).parse(); math_para=_el("m:oMathPara"); prop=_el("m:oMathParaPr"); prop.append(_el("m:jc",{"m:val":"centerGroup"})); math_para.append(prop); math=_el("m:oMath")
    for item in _sequence(nodes,size,color): math.append(item)
    math_para.append(math)
    wrapper=etree.Element("{http://schemas.microsoft.com/office/drawing/2010/main}m",nsmap={"a14":"http://schemas.microsoft.com/office/drawing/2010/main"})
    wrapper.append(math_para); paragraph._p.append(wrapper)


def add_native_equation(slide, latex: str, left: float, top: float, width: float, height: float, size: int = 24, color=(16,62,105)):
    box=slide.shapes.add_textbox(Inches(left),Inches(top),Inches(width),Inches(height)); frame=box.text_frame; frame.clear(); frame.word_wrap=False; frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    p=frame.paragraphs[0]; p.alignment=PP_ALIGN.CENTER; p._p.remove(p.runs[0]._r) if p.runs else None; append_omml(p,latex,size,color)
    return box

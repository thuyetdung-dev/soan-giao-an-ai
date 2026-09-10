export type FormulaVisual={type:"formula";latex:string;display?:boolean};
export type VariationVisual={type:"variation_table";x:string[];derivative:string[];values:string[]};
export type SignVisual={type:"sign_chart";x:string[];signs:string[];label?:string};
export type GraphVisual={type:"graph";expression:string;xMin:number;xMax:number;yMin:number;yMax:number;asymptotes?:{kind:"vertical"|"horizontal";value:number}[];points?:{x:number;y:number;label?:string}[]};
export type Visual=FormulaVisual|VariationVisual|SignVisual|GraphVisual;
export type Lesson={title:string;subject?:string;grade?:string;sections:{heading:string;content:string;visuals?:Visual[]}[]};

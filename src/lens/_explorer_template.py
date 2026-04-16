"""Explorer HTML template for Lens — self-contained, no CDN."""

EXPLORER_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Lens Explorer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f0f1a;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;display:flex;height:100vh;overflow:hidden}
#graph-area{flex:1;position:relative;overflow:hidden}
canvas#c{display:block;width:100%;height:100%}
#minimap{position:absolute;bottom:12px;left:12px;width:160px;height:110px;background:#12122a;border:1px solid #2a2a4e;border-radius:6px;overflow:hidden;opacity:.85;cursor:pointer}
#minimap:hover{opacity:1}
#sidebar{width:300px;background:#1a1a2e;border-left:1px solid #2a2a4e;display:flex;flex-direction:column;overflow:hidden}
#search-wrap{padding:12px;border-bottom:1px solid #2a2a4e}
#search{width:100%;background:#0f0f1a;border:1px solid #3a3a5e;color:#e0e0e0;padding:7px 10px;border-radius:6px;font-size:13px;outline:none}
#search:focus{border-color:#4e79a7}
#search-results{max-height:160px;overflow-y:auto;padding:4px 12px;border-bottom:1px solid #2a2a4e;display:none}
.sr-item{padding:5px 8px;cursor:pointer;border-radius:4px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-left:3px solid #555;margin:2px 0}
.sr-item:hover{background:#2a2a4e}
#toolbar-row{display:flex;gap:6px;padding:8px 12px;border-bottom:1px solid #2a2a4e}
#toolbar-row button{flex:1;padding:5px 0;background:#0f0f1a;border:1px solid #3a3a5e;color:#aaa;border-radius:4px;font-size:11px;cursor:pointer}
#toolbar-row button:hover{background:#2a2a4e;color:#fff}
#info-panel{padding:14px;border-bottom:1px solid #2a2a4e;min-height:150px;overflow-y:auto;max-height:40vh}
#info-panel h3{font-size:11px;color:#888;margin-bottom:8px;text-transform:uppercase;letter-spacing:.08em}
#info-content{font-size:13px;color:#ccc;line-height:1.7}
.field{margin-bottom:4px}.field b{color:#e0e0e0}
.empty{color:#555;font-style:italic}
.nbr-link{display:block;padding:3px 6px;margin:2px 0;border-radius:3px;cursor:pointer;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-left:3px solid #444}
.nbr-link:hover{background:#2a2a4e}
#legend-wrap{flex:1;overflow-y:auto;padding:12px}
#legend-wrap h3{font-size:11px;color:#888;margin-bottom:10px;text-transform:uppercase;letter-spacing:.08em}
.lg-item{display:flex;align-items:center;gap:8px;padding:4px 2px;cursor:pointer;border-radius:4px;font-size:12px}
.lg-item:hover{background:#2a2a4e;padding-left:6px}
.lg-item.dimmed{opacity:.3}
.lg-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0}
.lg-label{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lg-count{color:#666;font-size:11px;min-width:20px;text-align:right}
#stats-bar{padding:10px 14px;border-top:1px solid #2a2a4e;font-size:11px;color:#555}
#tooltip{position:absolute;background:rgba(20,20,40,.95);color:#ddd;padding:8px 12px;border-radius:6px;font-size:11px;pointer-events:none;display:none;border:1px solid #3a3a5e;z-index:100;max-width:350px}
#help-hint{position:absolute;top:10px;left:10px;font-size:10px;color:#444;pointer-events:none;transition:opacity .5s}
</style>
</head>
<body>
<div id="graph-area">
  <canvas id="c"></canvas>
  <canvas id="minimap"></canvas>
  <div id="tooltip"></div>
  <div id="help-hint">Scroll=zoom &middot; Drag=pan &middot; Click=inspect &middot; DblClick=focus &middot; Esc=deselect &middot; F=fit</div>
</div>
<div id="sidebar">
  <div id="search-wrap">
    <input id="search" type="text" placeholder="Search nodes..." autocomplete="off">
    <div id="search-results"></div>
  </div>
  <div id="toolbar-row">
    <button onclick="fitAll()">Fit All</button>
    <button onclick="deselect()">Deselect</button>
  </div>
  <div id="info-panel">
    <h3>Node Info</h3>
    <div id="info-content"><span class="empty">Click a node to inspect</span></div>
  </div>
  <div id="legend-wrap">
    <h3>Communities</h3>
    <div id="legend"></div>
  </div>
  <div id="stats-bar"></div>
</div>
<script>
const DATA=__GRAPH_JSON__;
const COLORS=["#4E79A7","#F28E2B","#E15759","#76B7B2","#59A14F","#EDC948","#B07AA1","#FF9DA7","#9C755F","#BAB0AC","#6a9955","#d7ba7d"];
const KIND_ICON={module:"\u{1F4E6}","class":"\u{1F3DB}","function":"\u{2699}",concept:"\u{1F4A1}",document:"\u{1F4C4}",file:"\u{1F4C1}",variable:"\u{1F4CC}"};

// ── Parse ────────────────────────────────────────────────
const rawNodes=DATA["@graph"].map(n=>{
  const l=n["lens:label"];
  const s=l.includes("\\")?l.split("\\").pop():l.includes("/")?l.split("/").pop():l;
  return{id:n["@id"],label:s,full:l,kind:n["lens:kind"],cluster:n["lens:cluster"]||null};
});
const rawEdges=(DATA["lens:edges"]||[]).map(e=>({
  src:e["lens:source"],tgt:e["lens:target"],rel:e["lens:relation"]
}));

// ── Degree ───────────────────────────────────────────────
const degMap={};rawNodes.forEach(n=>degMap[n.id]=0);
rawEdges.forEach(e=>{if(degMap[e.src]!==undefined)degMap[e.src]++;if(degMap[e.tgt]!==undefined)degMap[e.tgt]++;});
const maxDeg=Math.max(...Object.values(degMap),1);

// ── Clusters with readable names ─────────────────────────
const clusterMap={};
rawNodes.forEach(n=>{const c=n.cluster||"none";if(!clusterMap[c])clusterMap[c]={id:c,members:[],color:"",name:""};clusterMap[c].members.push(n);});
const cids=Object.keys(clusterMap);
cids.forEach((c,i)=>{
  const cl=clusterMap[c];
  cl.color=COLORS[i%COLORS.length];
  const sorted=[...cl.members].sort((a,b)=>(degMap[b.id]||0)-(degMap[a.id]||0));
  cl.name=sorted.slice(0,2).map(n=>n.label).join(", ")+(cl.members.length>2?" +\u2026":"");
});
rawNodes.forEach(n=>n.color=clusterMap[n.cluster||"none"].color);

// ── Adjacency ────────────────────────────────────────────
const adj={};rawNodes.forEach(n=>adj[n.id]=[]);
rawEdges.forEach(e=>{
  if(adj[e.src])adj[e.src].push({id:e.tgt,rel:e.rel});
  if(adj[e.tgt])adj[e.tgt].push({id:e.src,rel:e.rel});
});
const nodeById={};rawNodes.forEach(n=>nodeById[n.id]=n);
const neighborSet={};
rawNodes.forEach(n=>{neighborSet[n.id]=new Set((adj[n.id]||[]).map(x=>x.id));});

// ── Layout ───────────────────────────────────────────────
const canvas=document.getElementById("c");const ctx=canvas.getContext("2d");
let W,H;
function resize(){W=canvas.width=canvas.parentElement.clientWidth;H=canvas.height=canvas.parentElement.clientHeight;}
resize();window.addEventListener("resize",resize);
const cx=W/2,cy=H/2,baseR=Math.min(W,H)*0.36;
const visClusters=cids.filter(c=>clusterMap[c].members.length>0);
visClusters.forEach((c,i)=>{
  const a=2*Math.PI*i/Math.max(visClusters.length,1);
  const gcx=cx+baseR*Math.cos(a),gcy=cy+baseR*Math.sin(a);
  const members=clusterMap[c].members,spread=Math.min(100,18*Math.sqrt(members.length));
  members.forEach((n,j)=>{
    const a2=2*Math.PI*j/members.length;
    n.x=gcx+spread*Math.cos(a2)+(Math.random()-.5)*8;
    n.y=gcy+spread*Math.sin(a2)+(Math.random()-.5)*8;
    n.vx=0;n.vy=0;
  });
});

// ── Force sim ────────────────────────────────────────────
const idxMap={};rawNodes.forEach((n,i)=>idxMap[n.id]=i);
const eIdx=rawEdges.map(e=>[idxMap[e.src],idxMap[e.tgt]]).filter(e=>e[0]!==undefined&&e[1]!==undefined);
const N=rawNodes.length;
for(let t=0;t<Math.min(120,30+Math.floor(N/5));t++){
  for(let i=0;i<N;i++){
    const samples=N<200?N:12;
    for(let jj=0;jj<samples;jj++){
      const j=N<200?jj:((i*97+t*13+jj*7)%N);
      if(i===j)continue;
      let dx=rawNodes[j].x-rawNodes[i].x||.1,dy=rawNodes[j].y-rawNodes[i].y||.1;
      let d2=dx*dx+dy*dy,f=2500/Math.max(d2,80);
      rawNodes[i].vx-=dx*f;rawNodes[i].vy-=dy*f;
      if(N<200){rawNodes[j].vx+=dx*f;rawNodes[j].vy+=dy*f;}
    }
  }
  eIdx.forEach(([s,t2])=>{
    let dx=rawNodes[t2].x-rawNodes[s].x,dy=rawNodes[t2].y-rawNodes[s].y;
    rawNodes[s].vx+=dx*.003;rawNodes[s].vy+=dy*.003;
    rawNodes[t2].vx-=dx*.003;rawNodes[t2].vy-=dy*.003;
  });
  rawNodes.forEach(n=>{
    n.vx+=(cx-n.x)*.0004;n.vy+=(cy-n.y)*.0004;
    n.vx*=.82;n.vy*=.82;
    n.x+=n.vx;n.y+=n.vy;
    n.x=Math.max(40,Math.min(W-40,n.x));
    n.y=Math.max(40,Math.min(H-40,n.y));
  });
}

// ── View state ───────────────────────────────────────────
let scale=1,tx=0,ty=0;
const hiddenClusters=new Set();
let selectedId=null,hoveredId=null;
let animTarget=null,animStart=0;
const ANIM_DUR=400;

function toScreen(x,y){return[(x+tx)*scale+W/2,(y+ty)*scale+H/2];}
function toWorld(sx,sy){return[(sx-W/2)/scale-tx,(sy-H/2)/scale-ty];}

const allX=rawNodes.map(n=>n.x),allY=rawNodes.map(n=>n.y);
const minX=Math.min(...allX),maxX=Math.max(...allX);
const minY=Math.min(...allY),maxY=Math.max(...allY);
const gw=maxX-minX||1,gh=maxY-minY||1;
function fitAll(){scale=Math.min(W/(gw+120),H/(gh+120),2.5);tx=-(minX+gw/2);ty=-(minY+gh/2);}
fitAll();

function nodeRadius(n){return 4+14*(degMap[n.id]/maxDeg);}

// ── Shape drawing ────────────────────────────────────────
function drawShape(ctx,kind,sx,sy,r,fill,stroke,lw){
  ctx.fillStyle=fill;
  if(kind==="concept"||kind==="document"){
    ctx.beginPath();ctx.moveTo(sx,sy-r);ctx.lineTo(sx+r,sy);ctx.lineTo(sx,sy+r);ctx.lineTo(sx-r,sy);ctx.closePath();
    ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=lw;ctx.stroke();}
  } else if(kind==="module"||kind==="file"){
    const s=r*.82;
    const rr=s*.25;
    ctx.beginPath();ctx.moveTo(sx-s+rr,sy-s);ctx.arcTo(sx+s,sy-s,sx+s,sy+s,rr);ctx.arcTo(sx+s,sy+s,sx-s,sy+s,rr);ctx.arcTo(sx-s,sy+s,sx-s,sy-s,rr);ctx.arcTo(sx-s,sy-s,sx+s,sy-s,rr);ctx.closePath();
    ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=lw;ctx.stroke();}
  } else {
    ctx.beginPath();ctx.arc(sx,sy,r,0,Math.PI*2);ctx.fill();
    if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=lw;ctx.stroke();}
  }
}

// ── Draw loop ────────────────────────────────────────────
function draw(){
  if(animTarget){
    const p=Math.min((performance.now()-animStart)/ANIM_DUR,1);
    const e=1-Math.pow(1-p,3);
    scale+=(animTarget.s-scale)*e*.35;tx+=(animTarget.tx-tx)*e*.35;ty+=(animTarget.ty-ty)*e*.35;
    if(p>=1)animTarget=null;
  }
  ctx.clearRect(0,0,W,H);ctx.fillStyle="#0f0f1a";ctx.fillRect(0,0,W,H);

  const selNbrs=selectedId?neighborSet[selectedId]:null;

  // Edges
  rawEdges.forEach(e=>{
    const sn=nodeById[e.src],tn=nodeById[e.tgt];
    if(!sn||!tn||hiddenClusters.has(sn.cluster)||hiddenClusters.has(tn.cluster))return;
    const[x1,y1]=toScreen(sn.x,sn.y),[x2,y2]=toScreen(tn.x,tn.y);
    const isSel=selectedId&&(e.src===selectedId||e.tgt===selectedId);
    const isNbr=selNbrs&&(selNbrs.has(e.src)||selNbrs.has(e.tgt));
    // Dim when a selection exists and this edge is unrelated
    if(selectedId&&!isSel&&!isNbr){ctx.strokeStyle="rgba(40,40,60,.08)";ctx.lineWidth=.3;}
    else if(isSel){ctx.strokeStyle="rgba(78,121,167,.9)";ctx.lineWidth=2.2;}
    else{ctx.strokeStyle="rgba(80,80,120,.18)";ctx.lineWidth=.5/Math.sqrt(scale);}
    ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
    // Arrow
    if(isSel||scale>0.9){
      const ang=Math.atan2(y2-y1,x2-x1),r=nodeRadius(tn)*scale;
      const ax=x2-r*Math.cos(ang),ay=y2-r*Math.sin(ang),as=isSel?7:3;
      ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(ax,ay);
      ctx.lineTo(ax-as*Math.cos(ang-.35),ay-as*Math.sin(ang-.35));
      ctx.lineTo(ax-as*Math.cos(ang+.35),ay-as*Math.sin(ang+.35));ctx.fill();
    }
    // Edge label when selected & zoomed
    if(isSel&&scale>1.2&&e.rel){
      const mx=(x1+x2)/2,my=(y1+y2)/2;
      ctx.fillStyle="rgba(180,180,200,.55)";ctx.font="9px sans-serif";
      ctx.textAlign="center";ctx.textBaseline="bottom";ctx.fillText(e.rel,mx,my-3);
    }
  });

  // Nodes
  rawNodes.forEach(n=>{
    if(hiddenClusters.has(n.cluster))return;
    const[sx,sy]=toScreen(n.x,n.y),r=nodeRadius(n)*scale;
    if(sx<-r-20||sx>W+r+20||sy<-r-20||sy>H+r+20)return;
    const isSel=n.id===selectedId,isHov=n.id===hoveredId;
    const isNbr=selNbrs&&selNbrs.has(n.id);
    let alpha=1;if(selectedId&&!isSel&&!isNbr)alpha=0.12;
    ctx.globalAlpha=alpha;
    // Glow on neighbors
    if(isNbr&&!isSel){ctx.shadowColor=n.color;ctx.shadowBlur=14*Math.min(scale,2);}
    drawShape(ctx,n.kind,sx,sy,r,isSel?"#fff":n.color,(isSel||isHov)?"#fff":null,2);
    ctx.shadowBlur=0;
    // Label
    const deg=degMap[n.id];
    if(isSel||isHov||isNbr||deg>=maxDeg*.1||scale>2.2){
      ctx.fillStyle=isSel?"#fff":isNbr?"rgba(255,255,255,.9)":"rgba(220,220,230,.75)";
      ctx.font=(isSel?"bold ":"")+(isNbr?"12":"11")+"px 'Segoe UI',sans-serif";
      ctx.textAlign="left";ctx.textBaseline="middle";
      ctx.fillText(n.label.length>24?n.label.slice(0,22)+"\u2026":n.label,sx+r+4,sy);
    }
    ctx.globalAlpha=1;
  });

  drawMinimap();
  requestAnimationFrame(draw);
}

// ── Minimap ──────────────────────────────────────────────
const mmC=document.getElementById("minimap"),mmCtx=mmC.getContext("2d");
mmC.width=160;mmC.height=110;
function drawMinimap(){
  mmCtx.clearRect(0,0,160,110);mmCtx.fillStyle="#12122a";mmCtx.fillRect(0,0,160,110);
  const pad=8,mw=160-pad*2,mh=110-pad*2,ms=Math.min(mw/gw,mh/gh);
  rawNodes.forEach(n=>{
    if(hiddenClusters.has(n.cluster))return;
    mmCtx.fillStyle=n.id===selectedId?"#fff":n.color;
    mmCtx.fillRect(pad+(n.x-minX)*ms-1,pad+(n.y-minY)*ms-1,2,2);
  });
  const[v1x,v1y]=toWorld(0,0),[v2x,v2y]=toWorld(W,H);
  mmCtx.strokeStyle="rgba(78,121,167,.7)";mmCtx.lineWidth=1.2;
  mmCtx.strokeRect(pad+(v1x-minX)*ms,pad+(v1y-minY)*ms,(v2x-v1x)*ms,(v2y-v1y)*ms);
}
// Click minimap to navigate
mmC.addEventListener("click",e=>{
  const rect=mmC.getBoundingClientRect();
  const mx=e.clientX-rect.left,my=e.clientY-rect.top;
  const pad=8,ms=Math.min((160-pad*2)/gw,(110-pad*2)/gh);
  const wx=minX+(mx-pad)/ms,wy=minY+(my-pad)/ms;
  tx=-wx;ty=-wy;
});

draw();

// ── Interaction ──────────────────────────────────────────
let dragging=false,lastMX,lastMY;
canvas.addEventListener("wheel",e=>{
  e.preventDefault();
  const[wx,wy]=toWorld(e.offsetX,e.offsetY);
  scale*=e.deltaY>0?.9:1.1;scale=Math.max(.05,Math.min(20,scale));
  tx=-wx+(e.offsetX-W/2)/scale;ty=-wy+(e.offsetY-H/2)/scale;
},{passive:false});
canvas.addEventListener("mousedown",e=>{dragging=true;lastMX=e.offsetX;lastMY=e.offsetY;canvas.style.cursor="grabbing";});
canvas.addEventListener("mousemove",e=>{
  if(dragging){tx+=(e.offsetX-lastMX)/scale;ty+=(e.offsetY-lastMY)/scale;lastMX=e.offsetX;lastMY=e.offsetY;return;}
  const[wx,wy]=toWorld(e.offsetX,e.offsetY);
  let closest=null,minD=Infinity;
  rawNodes.forEach(n=>{
    if(hiddenClusters.has(n.cluster))return;
    const d=(n.x-wx)**2+(n.y-wy)**2,r=nodeRadius(n)/scale+5;
    if(d<r*r&&d<minD){minD=d;closest=n;}
  });
  hoveredId=closest?closest.id:null;
  canvas.style.cursor=hoveredId?"pointer":"grab";
  const tt=document.getElementById("tooltip");
  if(closest){
    const icon=KIND_ICON[closest.kind]||"";
    tt.style.display="block";
    tt.innerHTML="<b>"+icon+" "+esc(closest.label)+"</b><br><span style='color:#888'>"+esc(closest.kind)+" \u00B7 degree "+degMap[closest.id]+"</span>";
    tt.style.left=Math.min(e.offsetX+15,W-220)+"px";
    tt.style.top=Math.min(e.offsetY+15,H-60)+"px";
  } else tt.style.display="none";
});
canvas.addEventListener("mouseup",()=>{dragging=false;canvas.style.cursor="grab";});
canvas.addEventListener("mouseleave",()=>{dragging=false;document.getElementById("tooltip").style.display="none";});
canvas.addEventListener("click",e=>{
  if(hoveredId){selectedId=hoveredId;showInfo(hoveredId);}
  else deselect();
});
canvas.addEventListener("dblclick",e=>{if(hoveredId)animateFocus(hoveredId);});

// ── Keyboard ─────────────────────────────────────────────
document.addEventListener("keydown",e=>{
  if(e.target.tagName==="INPUT")return;
  if(e.key==="Escape")deselect();
  if(e.key==="f"||e.key==="F")fitAll();
});

// Fade help hint after 6 seconds
setTimeout(()=>{const h=document.getElementById("help-hint");if(h)h.style.opacity="0";},6000);

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function deselect(){selectedId=null;document.getElementById("info-content").innerHTML='<span class="empty">Click a node to inspect</span>';}

function animateFocus(nid){
  const n=nodeById[nid];if(!n)return;
  selectedId=nid;showInfo(nid);
  animTarget={s:2.5,tx:-n.x,ty:-n.y};animStart=performance.now();
}

function showInfo(nid){
  const n=nodeById[nid];if(!n)return;
  const nbrs=(adj[nid]||[]).sort((a,b)=>(degMap[b.id]||0)-(degMap[a.id]||0));
  const icon=KIND_ICON[n.kind]||"";
  const clName=clusterMap[n.cluster||"none"]?clusterMap[n.cluster||"none"].name:"";
  const nbrHtml=nbrs.slice(0,40).map(nb=>{
    const nn=nodeById[nb.id],c=nn?nn.color:"#555";
    return '<span class="nbr-link" style="border-left-color:'+c+'" onclick="animateFocus(\''+nb.id+'\')">'+esc(nn?nn.label:nb.id)+' <span style="color:#555;font-size:10px">'+esc(nb.rel)+'</span></span>';
  }).join("");
  document.getElementById("info-content").innerHTML=
    '<div class="field"><b>'+icon+' '+esc(n.label)+'</b></div>'+
    '<div class="field" style="color:#666;font-size:11px;word-break:break-all">'+esc(n.full)+'</div>'+
    '<div class="field">Kind: <b>'+esc(n.kind)+'</b></div>'+
    '<div class="field">Degree: <b>'+degMap[nid]+'</b></div>'+
    '<div class="field">Cluster: <span style="color:'+n.color+'">\u25CF</span> '+esc(clName)+'</div>'+
    (nbrs.length?'<div class="field" style="margin-top:10px;color:#888;font-size:11px;text-transform:uppercase;letter-spacing:.05em">Neighbors ('+nbrs.length+')</div><div style="max-height:180px;overflow-y:auto;margin-top:4px">'+nbrHtml+'</div>':"");
}

// ── Search ───────────────────────────────────────────────
const searchInput=document.getElementById("search"),searchResults=document.getElementById("search-results");
searchInput.addEventListener("input",()=>{
  const q=searchInput.value.toLowerCase().trim();searchResults.innerHTML="";
  if(!q){searchResults.style.display="none";return;}
  const matches=rawNodes.filter(n=>n.label.toLowerCase().includes(q)||n.full.toLowerCase().includes(q))
    .sort((a,b)=>(degMap[b.id]||0)-(degMap[a.id]||0)).slice(0,20);
  if(!matches.length){searchResults.style.display="none";return;}
  searchResults.style.display="block";
  matches.forEach(n=>{
    const el=document.createElement("div");el.className="sr-item";
    el.innerHTML='<span style="color:'+n.color+'">\u25CF</span> '+esc(n.label)+' <span style="color:#555;font-size:10px">'+esc(n.kind)+'</span>';
    el.style.borderLeftColor=n.color;
    el.onclick=()=>{animateFocus(n.id);searchResults.style.display="none";searchInput.value="";};
    searchResults.appendChild(el);
  });
});
searchInput.addEventListener("keydown",e=>{if(e.key==="Enter"){
  const q=searchInput.value.toLowerCase().trim();
  const m=rawNodes.find(n=>n.label.toLowerCase().includes(q));
  if(m){animateFocus(m.id);searchResults.style.display="none";searchInput.value="";}
}});
document.addEventListener("click",e=>{
  if(!searchResults.contains(e.target)&&e.target!==searchInput)searchResults.style.display="none";
});

// ── Legend ────────────────────────────────────────────────
const legendEl=document.getElementById("legend");
Object.values(clusterMap).filter(c=>c.members.length>1).sort((a,b)=>b.members.length-a.members.length).slice(0,30).forEach(c=>{
  const item=document.createElement("div");item.className="lg-item";
  item.innerHTML='<div class="lg-dot" style="background:'+c.color+'"></div><span class="lg-label" title="'+esc(c.name)+'">'+esc(c.name)+'</span><span class="lg-count">'+c.members.length+'</span>';
  item.onclick=()=>{
    if(hiddenClusters.has(c.id)){hiddenClusters.delete(c.id);item.classList.remove("dimmed");}
    else{hiddenClusters.add(c.id);item.classList.add("dimmed");}
  };
  legendEl.appendChild(item);
});

document.getElementById("stats-bar").textContent=rawNodes.length+" nodes \u00B7 "+rawEdges.length+" edges \u00B7 "+visClusters.length+" communities";
</script>
</body>
</html>'''

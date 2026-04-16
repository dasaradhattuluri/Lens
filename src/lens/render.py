"""Rendering: interactive HTML explorer and Markdown analysis report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lens.graph import KnowledgeGraph


# ---------------------------------------------------------------------------
# HTML Explorer (self-contained, no CDN — uses inline <script>)
# ---------------------------------------------------------------------------

_EXPLORER_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Lens Explorer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f0f1a;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;display:flex;height:100vh;overflow:hidden}
#graph-area{flex:1;position:relative;overflow:hidden}
canvas{display:block;width:100%;height:100%}
#sidebar{width:300px;background:#1a1a2e;border-left:1px solid #2a2a4e;display:flex;flex-direction:column;overflow:hidden}
#search-wrap{padding:12px;border-bottom:1px solid #2a2a4e}
#search{width:100%;background:#0f0f1a;border:1px solid #3a3a5e;color:#e0e0e0;padding:7px 10px;border-radius:6px;font-size:13px;outline:none}
#search:focus{border-color:#4e79a7}
#search-results{max-height:160px;overflow-y:auto;padding:4px 12px;border-bottom:1px solid #2a2a4e;display:none}
.sr-item{padding:5px 8px;cursor:pointer;border-radius:4px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-left:3px solid #555;margin:2px 0}
.sr-item:hover{background:#2a2a4e}
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
.lg-count{color:#666;font-size:11px}
#stats-bar{padding:10px 14px;border-top:1px solid #2a2a4e;font-size:11px;color:#555}
#tooltip{position:absolute;background:#222;color:#ddd;padding:6px 10px;border-radius:4px;font-size:11px;pointer-events:none;display:none;border:1px solid #444;z-index:100;max-width:350px}
</style>
</head>
<body>
<div id="graph-area">
  <canvas id="c"></canvas>
  <div id="tooltip"></div>
</div>
<div id="sidebar">
  <div id="search-wrap">
    <input id="search" type="text" placeholder="Search nodes..." autocomplete="off">
    <div id="search-results"></div>
  </div>
  <div id="info-panel">
    <h3>Node Info</h3>
    <div id="info-content"><span class="empty">Click a node to inspect</span></div>
  </div>
  <div id="legend-wrap">
    <h3>Communities</h3>
    <div id="legend"></div>
  </div>
  <div id="stats-bar" id="stats"></div>
</div>
<script>
const DATA=__GRAPH_JSON__;
const COLORS=["#4E79A7","#F28E2B","#E15759","#76B7B2","#59A14F","#EDC948","#B07AA1","#FF9DA7","#9C755F","#BAB0AC","#6a9955","#d7ba7d"];

// Parse graph data
const rawNodes=DATA["@graph"].map(n=>{
  const l=n["lens:label"];
  const s=l.includes("\\\\")?l.split("\\\\").pop():l.includes("/")?l.split("/").pop():l;
  return{id:n["@id"],label:s,full:l,kind:n["lens:kind"],cluster:n["lens:cluster"]||null};
});
const rawEdges=(DATA["lens:edges"]||[]).map(e=>({
  src:e["lens:source"],tgt:e["lens:target"],rel:e["lens:relation"]
}));

// Compute degree
const degMap={};
rawNodes.forEach(n=>degMap[n.id]=0);
rawEdges.forEach(e=>{if(degMap[e.src]!==undefined)degMap[e.src]++;if(degMap[e.tgt]!==undefined)degMap[e.tgt]++;});
const maxDeg=Math.max(...Object.values(degMap),1);

// Cluster info
const clusterMap={};
rawNodes.forEach(n=>{const c=n.cluster||"none";if(!clusterMap[c])clusterMap[c]={id:c,members:[],color:""};clusterMap[c].members.push(n);});
const cids=Object.keys(clusterMap);
cids.forEach((c,i)=>clusterMap[c].color=COLORS[i%COLORS.length]);
rawNodes.forEach(n=>n.color=clusterMap[n.cluster||"none"].color);

// Adjacency for neighbor lookup
const adj={};
rawNodes.forEach(n=>adj[n.id]=[]);
rawEdges.forEach(e=>{
  if(adj[e.src])adj[e.src].push({id:e.tgt,rel:e.rel});
  if(adj[e.tgt])adj[e.tgt].push({id:e.src,rel:e.rel});
});
const nodeById={};rawNodes.forEach(n=>nodeById[n.id]=n);

// Layout: cluster-circle with sub-positions
const canvas=document.getElementById("c");
const ctx=canvas.getContext("2d");
let W,H;
function resize(){W=canvas.width=canvas.parentElement.clientWidth;H=canvas.height=canvas.parentElement.clientHeight;}
resize(); window.addEventListener("resize",resize);

const cx=W/2,cy=H/2,baseR=Math.min(W,H)*0.36;
// Only layout clusters with >0 members that are not hidden singletons
const visClusters=cids.filter(c=>clusterMap[c].members.length>0);
visClusters.forEach((c,i)=>{
  const a=2*Math.PI*i/Math.max(visClusters.length,1);
  const gcx=cx+baseR*Math.cos(a),gcy=cy+baseR*Math.sin(a);
  const members=clusterMap[c].members;
  const spread=Math.min(100,18*Math.sqrt(members.length));
  members.forEach((n,j)=>{
    const a2=2*Math.PI*j/members.length;
    n.x=gcx+spread*Math.cos(a2)+(Math.random()-.5)*8;
    n.y=gcy+spread*Math.sin(a2)+(Math.random()-.5)*8;
    n.vx=0;n.vy=0;
  });
});

// Force simulation
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

// Rendering state
let scale=1,tx=0,ty=0;
const hiddenClusters=new Set();
let selectedId=null,hoveredId=null;

function toScreen(x,y){return[(x+tx)*scale+W/2,(y+ty)*scale+H/2];}
function toWorld(sx,sy){return[(sx-W/2)/scale-tx,(sy-H/2)/scale-ty];}

// Center the graph initially
const minX=Math.min(...rawNodes.map(n=>n.x)),maxX=Math.max(...rawNodes.map(n=>n.x));
const minY=Math.min(...rawNodes.map(n=>n.y)),maxY=Math.max(...rawNodes.map(n=>n.y));
const gw=maxX-minX||1,gh=maxY-minY||1;
scale=Math.min(W/(gw+100),H/(gh+100),2);
tx=-(minX+gw/2);ty=-(minY+gh/2);

function nodeRadius(n){return 4+12*(degMap[n.id]/maxDeg);}

function draw(){
  ctx.clearRect(0,0,W,H);
  ctx.fillStyle="#0f0f1a";ctx.fillRect(0,0,W,H);

  // Edges
  ctx.lineWidth=.8/Math.sqrt(scale);
  rawEdges.forEach(e=>{
    const sn=nodeById[e.src],tn=nodeById[e.tgt];
    if(!sn||!tn)return;
    if(hiddenClusters.has(sn.cluster)||hiddenClusters.has(tn.cluster))return;
    const[x1,y1]=toScreen(sn.x,sn.y),[x2,y2]=toScreen(tn.x,tn.y);
    const isSel=selectedId&&(e.src===selectedId||e.tgt===selectedId);
    ctx.strokeStyle=isSel?"rgba(78,121,167,.8)":"rgba(80,80,110,.25)";
    ctx.lineWidth=isSel?2:(.6/Math.sqrt(scale));
    ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
    // Arrow
    if(isSel||scale>0.8){
      const ang=Math.atan2(y2-y1,x2-x1);
      const r=nodeRadius(tn)*scale;
      const ax=x2-r*Math.cos(ang),ay=y2-r*Math.sin(ang);
      const as=isSel?6:3;
      ctx.fillStyle=ctx.strokeStyle;
      ctx.beginPath();
      ctx.moveTo(ax,ay);
      ctx.lineTo(ax-as*Math.cos(ang-.4),ay-as*Math.sin(ang-.4));
      ctx.lineTo(ax-as*Math.cos(ang+.4),ay-as*Math.sin(ang+.4));
      ctx.fill();
    }
  });

  // Nodes
  rawNodes.forEach(n=>{
    if(hiddenClusters.has(n.cluster))return;
    const[sx,sy]=toScreen(n.x,n.y);
    const r=nodeRadius(n)*scale;
    if(sx<-r||sx>W+r||sy<-r||sy>H+r)return; // frustum cull
    const isSel=n.id===selectedId;
    const isHov=n.id===hoveredId;
    ctx.beginPath();ctx.arc(sx,sy,r,0,Math.PI*2);
    ctx.fillStyle=isSel?"#ffffff":n.color;
    ctx.fill();
    if(isSel||isHov){ctx.strokeStyle="#fff";ctx.lineWidth=2;ctx.stroke();}
    // Label: show for high-degree or selected/hovered, or when zoomed in
    const deg=degMap[n.id];
    if(isSel||isHov||deg>=maxDeg*.12||scale>1.8){
      ctx.fillStyle=isSel?"#fff":"rgba(224,224,224,.85)";
      ctx.font=(isSel?"bold ":"")+"11px 'Segoe UI',sans-serif";
      ctx.textAlign="left";ctx.textBaseline="middle";
      const lbl=n.label.length>22?n.label.slice(0,20)+"…":n.label;
      ctx.fillText(lbl,sx+r+4,sy);
    }
  });
  requestAnimationFrame(draw);
}
draw();

// Interaction: pan, zoom, hover, click
let dragging=false,lastMX,lastMY;
canvas.addEventListener("wheel",e=>{
  e.preventDefault();
  const[wx,wy]=toWorld(e.offsetX,e.offsetY);
  scale*=e.deltaY>0?.9:1.1;
  scale=Math.max(.05,Math.min(20,scale));
  tx=-(wx)+(e.offsetX-W/2)/scale;
  ty=-(wy)+(e.offsetY-H/2)/scale;
},{passive:false});

canvas.addEventListener("mousedown",e=>{dragging=true;lastMX=e.offsetX;lastMY=e.offsetY;});
canvas.addEventListener("mousemove",e=>{
  if(dragging){tx+=(e.offsetX-lastMX)/scale;ty+=(e.offsetY-lastMY)/scale;lastMX=e.offsetX;lastMY=e.offsetY;return;}
  const[wx,wy]=toWorld(e.offsetX,e.offsetY);
  let closest=null,minD=Infinity;
  rawNodes.forEach(n=>{
    if(hiddenClusters.has(n.cluster))return;
    const d=(n.x-wx)**2+(n.y-wy)**2;
    const r=nodeRadius(n)/scale+5;
    if(d<r*r&&d<minD){minD=d;closest=n;}
  });
  hoveredId=closest?closest.id:null;
  canvas.style.cursor=hoveredId?"pointer":"default";
  const tt=document.getElementById("tooltip");
  if(closest){
    tt.style.display="block";
    tt.innerHTML="<b>"+esc(closest.label)+"</b><br>"+esc(closest.kind)+" &middot; deg "+degMap[closest.id];
    tt.style.left=(e.offsetX+15)+"px";tt.style.top=(e.offsetY+15)+"px";
  } else tt.style.display="none";
});
canvas.addEventListener("mouseup",()=>{dragging=false;});
canvas.addEventListener("mouseleave",()=>{dragging=false;document.getElementById("tooltip").style.display="none";});
canvas.addEventListener("click",e=>{
  if(hoveredId){selectedId=hoveredId;showInfo(hoveredId);}
  else{selectedId=null;document.getElementById("info-content").innerHTML='<span class="empty">Click a node to inspect</span>';}
});
canvas.addEventListener("dblclick",e=>{
  if(hoveredId){focusNode(hoveredId);}
});

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function showInfo(nid){
  const n=nodeById[nid];if(!n)return;
  const neighbors=adj[nid]||[];
  const nbrHtml=neighbors.slice(0,30).map(nb=>{
    const nn=nodeById[nb.id];
    const c=nn?nn.color:"#555";
    return '<span class="nbr-link" style="border-left-color:'+c+'" onclick="focusNode(\\''+nb.id+'\\')">'+esc(nn?nn.label:nb.id)+' <span style="color:#666;font-size:10px">'+esc(nb.rel)+'</span></span>';
  }).join("");
  document.getElementById("info-content").innerHTML=
    '<div class="field"><b>'+esc(n.label)+'</b></div>'+
    '<div class="field" style="color:#888;font-size:11px;word-break:break-all">'+esc(n.full)+'</div>'+
    '<div class="field">Kind: '+esc(n.kind)+'</div>'+
    '<div class="field">Degree: '+degMap[nid]+'</div>'+
    '<div class="field">Cluster: <span style="color:'+n.color+'">\\u25CF</span> '+(n.cluster?n.cluster.split(":").pop().slice(0,8):"none")+'</div>'+
    (neighbors.length?'<div class="field" style="margin-top:8px;color:#888;font-size:11px">Neighbors ('+neighbors.length+')</div><div style="max-height:150px;overflow-y:auto">'+nbrHtml+'</div>':"");
}

function focusNode(nid){
  const n=nodeById[nid];if(!n)return;
  selectedId=nid;
  scale=2;tx=-n.x;ty=-n.y;
  showInfo(nid);
}

// Search
const searchInput=document.getElementById("search");
const searchResults=document.getElementById("search-results");
searchInput.addEventListener("input",()=>{
  const q=searchInput.value.toLowerCase().trim();
  searchResults.innerHTML="";
  if(!q){searchResults.style.display="none";return;}
  const matches=rawNodes.filter(n=>n.label.toLowerCase().includes(q)||n.full.toLowerCase().includes(q)).slice(0,20);
  if(!matches.length){searchResults.style.display="none";return;}
  searchResults.style.display="block";
  matches.forEach(n=>{
    const el=document.createElement("div");
    el.className="sr-item";el.textContent=n.label;
    el.style.borderLeftColor=n.color;
    el.onclick=()=>{focusNode(n.id);searchResults.style.display="none";searchInput.value="";};
    searchResults.appendChild(el);
  });
});
document.addEventListener("click",e=>{
  if(!searchResults.contains(e.target)&&e.target!==searchInput)searchResults.style.display="none";
});

// Legend
const legendEl=document.getElementById("legend");
// Sort clusters by member count descending, show top 30
const sortedClusters=Object.values(clusterMap).filter(c=>c.members.length>1).sort((a,b)=>b.members.length-a.members.length).slice(0,30);
sortedClusters.forEach(c=>{
  const item=document.createElement("div");
  item.className="lg-item";
  item.innerHTML='<div class="lg-dot" style="background:'+c.color+'"></div><span class="lg-label">'+esc(c.id.split(":").pop().slice(0,8))+" ("+c.members.length+')</span>';
  item.onclick=()=>{
    if(hiddenClusters.has(c.id)){hiddenClusters.delete(c.id);item.classList.remove("dimmed");}
    else{hiddenClusters.add(c.id);item.classList.add("dimmed");}
  };
  legendEl.appendChild(item);
});

// Stats
document.getElementById("stats-bar").textContent=rawNodes.length+" nodes \\u00B7 "+rawEdges.length+" edges \\u00B7 "+cids.length+" clusters";
</script>
</body>
</html>
"""


def render_explorer_html(kg: KnowledgeGraph, dest: str | Path, corpus_root: str = ".") -> None:
    """Write a self-contained interactive HTML explorer to *dest*."""
    from lens._explorer_template import EXPLORER_HTML

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    graph_json = json.dumps(kg.to_jsonld(corpus_root))
    html = EXPLORER_HTML.replace("__GRAPH_JSON__", graph_json)
    dest.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Markdown analysis report
# ---------------------------------------------------------------------------

def render_analysis_report(kg: KnowledgeGraph, dest: str | Path, corpus_root: str = ".") -> None:
    """Write a structured Markdown analysis report to *dest*."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    sections.append("# Lens Analysis Report\n")

    # --- Summary stats ---
    files = {n.provenance.source_file for n in kg.nodes.values()}
    sections.append("## Corpus Summary\n")
    sections.append(f"| Metric | Value |")
    sections.append(f"|---|---|")
    sections.append(f"| Files analysed | {len(files)} |")
    sections.append(f"| Nodes | {len(kg.nodes)} |")
    sections.append(f"| Edges | {len(kg.edges)} |")
    sections.append(f"| Clusters | {len(kg.clusters)} |")
    sections.append("")

    # --- High-degree nodes (god nodes) ---
    if kg.nodes:
        degree_map: dict[str, int] = {}
        for edge in kg.edges.values():
            degree_map[edge.source_id] = degree_map.get(edge.source_id, 0) + 1
            degree_map[edge.target_id] = degree_map.get(edge.target_id, 0) + 1
        top_nodes = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)[:10]
        if top_nodes:
            sections.append("## High-Connectivity Nodes\n")
            sections.append("These are the most-connected entities in the graph — key "
                            "integration points that many other components depend on or "
                            "reference.\n")
            sections.append("| Rank | Label | Kind | Degree |")
            sections.append("|---|---|---|---|")
            for rank, (nid, deg) in enumerate(top_nodes, 1):
                node = kg.nodes.get(nid)
                if node:
                    sections.append(f"| {rank} | {node.label} | {node.kind.value} | {deg} |")
            sections.append("")

    # --- Cross-cluster bridge edges ---
    if kg.clusters:
        bridge_edges = []
        for edge in kg.edges.values():
            src = kg.nodes.get(edge.source_id)
            tgt = kg.nodes.get(edge.target_id)
            if src and tgt and src.cluster_id and tgt.cluster_id and src.cluster_id != tgt.cluster_id:
                bridge_edges.append((src, tgt, edge))
        if bridge_edges:
            sections.append("## Cross-Cluster Connections\n")
            sections.append("Edges that bridge different clusters — these often reveal "
                            "unexpected architectural couplings.\n")
            sections.append("| Source | Target | Relation |")
            sections.append("|---|---|---|")
            for src, tgt, edge in bridge_edges[:20]:
                sections.append(f"| {src.label} | {tgt.label} | {edge.relation.value} |")
            if len(bridge_edges) > 20:
                sections.append(f"\n… and {len(bridge_edges) - 20} more cross-cluster edges.\n")
            sections.append("")

    # --- Cluster descriptions ---
    if kg.clusters:
        sections.append("## Clusters\n")
        for cluster in kg.clusters.values():
            sections.append(f"### {cluster.label}\n")
            sections.append(f"{cluster.summary}\n")
            sections.append(f"Members ({len(cluster.member_ids)}):\n")
            for mid in cluster.member_ids[:20]:
                node = kg.nodes.get(mid)
                lbl = node.label if node else mid
                sections.append(f"- {lbl}")
            if len(cluster.member_ids) > 20:
                sections.append(f"- … and {len(cluster.member_ids) - 20} more")
            sections.append("")

    # --- Key entity inventory ---
    sections.append("## Key Entities\n")
    sections.append("| Label | Kind | Source |")
    sections.append("|---|---|---|")
    for node in list(kg.nodes.values())[:50]:
        sections.append(
            f"| {node.label} | {node.kind.value} | {node.provenance.source_file} |"
        )
    if len(kg.nodes) > 50:
        sections.append(f"\n… and {len(kg.nodes) - 50} more entities.\n")
    sections.append("")

    # --- Integrity / coverage audit ---
    sections.append("## Integrity Audit\n")
    orphan_nodes = [
        n for n in kg.nodes.values()
        if not any(
            e.source_id == n.uid or e.target_id == n.uid
            for e in kg.edges.values()
        )
    ]
    sections.append(f"- Orphan nodes (no edges): **{len(orphan_nodes)}**")
    dangling = [
        e for e in kg.edges.values()
        if e.source_id not in kg.nodes or e.target_id not in kg.nodes
    ]
    sections.append(f"- Dangling edges (missing endpoint): **{len(dangling)}**")
    sections.append("")

    dest.write_text("\n".join(sections), encoding="utf-8")

"""Build page/index.html from runs/latest.json (or a run file given as argv[1])."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "runs" / "latest.json"
run = json.loads(src.read_text())
(ROOT / "page").mkdir(exist_ok=True)

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Habibi Lead Run</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--ink:#17202a;--mute:#5f6b7a;--line:#e3e6ea;--acc:#0a66c2;--ok:#1a7f4b;--warn:#b7791f;--bad:#b42318;--chip:#eef2f6}
:root:not([data-theme="light"]){@media (prefers-color-scheme:dark){--bg:#0f1317;--card:#171c22;--ink:#e8ecf1;--mute:#9aa6b4;--line:#2a323c;--acc:#5aa6ff;--chip:#222a33}}
:root[data-theme="dark"]{--bg:#0f1317;--card:#171c22;--ink:#e8ecf1;--mute:#9aa6b4;--line:#2a323c;--acc:#5aa6ff;--chip:#222a33}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:15px;margin:24px 0 10px;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.sub{color:var(--mute);margin-bottom:16px}
.funnel{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.stage{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.stage b{display:block;font-size:26px;font-weight:600}
.stage span{color:var(--mute);font-size:12px}
.spend{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.spend .stage{flex:1;min-width:180px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:8px}
.card.off{opacity:.55}
.who{display:flex;gap:10px;align-items:center}
.ava{width:40px;height:40px;border-radius:50%;background:var(--chip);display:flex;align-items:center;justify-content:center;font-weight:600;color:var(--acc);flex:none}
.who .n{font-weight:600}
.who .h{color:var(--mute);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:240px}
.body{white-space:pre-wrap;max-height:150px;overflow:hidden;position:relative;font-size:13px}
.body.open{max-height:none}
.more{color:var(--acc);cursor:pointer;font-size:12px;background:none;border:0;padding:0;text-align:left}
.meta{display:flex;gap:12px;color:var(--mute);font-size:12px;flex-wrap:wrap;align-items:center}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;background:var(--chip);font-size:12px}
.pill.ok{background:color-mix(in srgb,var(--ok) 18%,transparent);color:var(--ok)}
.pill.warn{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn)}
.pill.bad{background:color-mix(in srgb,var(--bad) 15%,transparent);color:var(--bad)}
.pill.acc{background:color-mix(in srgb,var(--acc) 15%,transparent);color:var(--acc)}
.bar{height:6px;border-radius:3px;background:var(--chip);overflow:hidden}
.bar i{display:block;height:100%;background:var(--acc)}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;align-items:center}
select,input{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font:inherit}
.split{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:12px}
@media (max-width:900px){.split{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--mute);font-weight:600;position:sticky;top:0;background:var(--card)}
tr.row{cursor:pointer}
tr.row:hover,tr.row.sel{background:color-mix(in srgb,var(--acc) 8%,transparent)}
td.h{color:var(--mute);font-size:12px;max-width:380px}
.tbl{max-height:70vh;overflow:auto;border-radius:10px}
.insp{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;position:sticky;top:12px;max-height:calc(100vh - 24px);overflow:auto}
.insp h3{margin:0 0 2px;font-size:16px}
.insp .k{color:var(--mute);font-size:11px;text-transform:uppercase;letter-spacing:.04em;margin:14px 0 6px}
.dist{display:grid;grid-template-columns:120px 1fr 44px;gap:6px;align-items:center;font-size:12px;margin:3px 0}
.sig{font-size:13px;margin:4px 0;padding:6px 8px;background:var(--chip);border-radius:6px}
a{color:var(--acc);text-decoration:none}
code{font-size:12px;background:var(--chip);padding:1px 5px;border-radius:4px}
.empty{color:var(--mute);padding:20px;text-align:center}
</style>
</head>
<body>
<div class="wrap">
<h1>Habibi lead run</h1>
<div class="sub" id="sub"></div>

<h2>Funnel</h2>
<div class="funnel" id="funnel"></div>
<div class="spend" id="spend"></div>

<h2>Posts</h2>
<div class="filters"><label><input type="checkbox" id="showOff"> show off-topic posts</label></div>
<div class="cards" id="posts"></div>

<h2>People</h2>
<div class="filters">
  <select id="fTier"><option value="">all tiers</option><option value="decision_maker">decision makers</option><option value="user">users</option><option value="not_lead">not leads</option></select>
  <select id="fRole"><option value="">all roles</option></select>
  <select id="fEmail"><option value="">any contact</option><option value="hit">email found</option><option value="miss">email missed</option></select>
  <input id="fQ" placeholder="search name or headline">
  <span id="count" style="color:var(--mute)"></span>
</div>
<div class="split">
  <div class="tbl"><table><thead><tr><th>#</th><th>Person</th><th>Fit</th><th>Role</th><th>Signals</th><th>Email</th></tr></thead><tbody id="people"></tbody></table></div>
  <div class="insp" id="insp"><div class="empty">Select a person to inspect</div></div>
</div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const run=JSON.parse(document.getElementById('data').textContent);
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pct=p=>Math.round((p||0)*100)+'%';
const initials=n=>(n||'?').split(/\s+/).slice(0,2).map(w=>w[0]||'').join('').toUpperCase();
const postById=Object.fromEntries(run.posts.map(p=>[p.id,p]));

$('#sub').textContent=`${run.ran_at} · topics: ${run.topics.join(' · ')} · judge: ${run.config.judge_backend}${run.config.judge_backend==='agent'?' (stand-in: slower, dearer per decision, not calibrated like jev)':''}`;

const f=run.funnel;
$('#funnel').innerHTML=[['posts found',f.posts_found],['judged (top by likes)',f.posts_judged],['on topic ≥ '+run.config.topic_min_p,f.posts_on_topic],['people engaged',f.people],['decision makers (fit ≥ '+run.config.fit_min+')',f.decision_makers],['emails found',f.emails]]
  .map(([l,v])=>`<div class="stage"><b>${v}</b><span>${l}</span></div>`).join('');

const s=run.spend;
const byTool={};for(const c of s.treg_calls){byTool[c.tool]=(byTool[c.tool]||0)+c.charged}
$('#spend').innerHTML=`<div class="stage"><b>$${s.treg_usd.toFixed(4)}</b><span>treg spend · ${s.treg_calls.length} calls<br>${Object.entries(byTool).map(([t,v])=>`${t.replace('harvestapi.linkedin.','').replace('treg.people.','')} $${v.toFixed(4)}`).join(' · ')}</span></div>
<div class="stage"><b>$${(s.jev_usd||0).toFixed(4)}</b><span>jev spend · ${s.jev_calls||0} calls</span></div>
${s.claude_calls?`<div class="stage"><b>$${(s.claude_usd||0).toFixed(4)}</b><span>Claude Haiku 5.5 stand-in judge · ${s.claude_calls} calls · ${s.claude_tokens_in} in / ${s.claude_tokens_out} out tokens</span></div>`:''}
${s.agent_calls?`<div class="stage"><b>–</b><span>${s.agent_calls} judgements by agent stand-in (not billed here)</span></div>`:''}`;

function renderPosts(){
  const showOff=$('#showOff').checked;
  const posts=run.posts.filter(p=>showOff||p.kept);
  $('#posts').innerHTML=posts.map(p=>{
    const q=p.about_topic||{};
    const cls=p.on_topic_p>=run.config.topic_min_p?'ok':(p.on_topic_p>=0.4?'warn':'bad');
    return `<div class="card ${p.kept?'':'off'}">
      <div class="who"><div class="ava">${esc(initials(p.author.name))}</div><div><div class="n"><a href="${esc(p.author.url||'#')}" target="_blank">${esc(p.author.name)}</a></div><div class="h" title="${esc(p.author.headline)}">${esc(p.author.headline||'')}</div></div></div>
      <div class="body" id="b${p.id}">${esc(p.content)}</div>
      <button class="more" onclick="document.getElementById('b${p.id}').classList.toggle('open');this.textContent=this.textContent==='…more'?'less':'…more'">…more</button>
      <div class="meta"><span>👍 ${p.likes}</span><span>💬 ${p.comments}</span><span>↗ ${p.shares}</span><span>#${p.rank}</span><a href="${esc(p.url)}" target="_blank">open</a></div>
      <div class="meta"><span class="pill ${cls}">on topic ${pct(p.on_topic_p)}</span>${p.kept?`<span class="pill acc">kept · ${p.n_reactions} reactions · ${p.n_comments} comments</span>`:''}<span class="pill">${esc((p.topics||[]).join(', '))}</span><span class="pill">judge: ${esc(p.judge||'')}</span></div>
      <div class="bar"><i style="width:${pct(p.on_topic_p)}"></i></div>
    </div>`}).join('')||'<div class="empty">no posts</div>';
}
$('#showOff').onchange=renderPosts;renderPosts();

const roles=[...new Set(run.people.map(w=>w.role?.choice).filter(Boolean))].sort();
$('#fRole').innerHTML+=roles.map(r=>`<option>${r}</option>`).join('');
let sel=null;
function renderPeople(){
  const t=$('#fTier').value,r=$('#fRole').value,e=$('#fEmail').value,q=$('#fQ').value.toLowerCase();
  const rows=run.people.filter(w=>(!t||w.tier===t)&&(!r||w.role?.choice===r)&&(!e||w.email?.status===e)&&(!q||(w.name+' '+(w.headline||'')).toLowerCase().includes(q)));
  $('#count').textContent=`${rows.length} of ${run.people.length}`;
  $('#people').innerHTML=rows.map((w,i)=>{
    const tc=w.tier==='decision_maker'?'ok':(w.tier==='user'?'warn':'');
    const em=w.email?(w.email.status==='hit'?`<span class="pill ok">${esc(w.email.email)}</span>${w.email.verify?` <span class="pill ${/safe|valid/.test(w.email.verify.verdict)?'ok':'warn'}">${esc(w.email.verify.verdict)}</span>`:''}`:`<span class="pill bad">${esc(w.email.status)}</span>`):'';
    return `<tr class="row ${sel===w.id?'sel':''}" data-id="${esc(w.id)}"><td>${i+1}</td><td><b>${esc(w.name)}</b><div class="h" style="color:var(--mute);font-size:12px">${esc(w.headline||'')}</div></td><td><span class="pill ${tc}">${w.fit?.score?.toFixed(2)??'–'}</span></td><td>${esc(w.role?.choice||'')}</td><td>${w.signals.map(s=>s.type==='reaction'?esc(s.reaction.toLowerCase()):'💬').join(' ')}</td><td>${em}</td></tr>`}).join('')||'<tr><td colspan="6" class="empty">nobody matches</td></tr>';
  for(const tr of $('#people').querySelectorAll('tr.row'))tr.onclick=()=>{sel=tr.dataset.id;renderPeople();renderInsp()};
}
function dist(obj,labels){return Object.entries(obj||{}).map(([k,v])=>`<div class="dist"><span>${esc(labels?.[k]??k)}</span><div class="bar"><i style="width:${pct(v)}"></i></div><span>${pct(v)}</span></div>`).join('')}
function renderInsp(){
  const w=run.people.find(x=>x.id===sel);if(!w){$('#insp').innerHTML='<div class="empty">Select a person to inspect</div>';return}
  const fitLabels={'0':'not a lead','1':'user','2':'decision maker'};
  const em=w.email;
  $('#insp').innerHTML=`<h3><a href="${esc(w.url||'#')}" target="_blank">${esc(w.name)}</a></h3><div style="color:var(--mute);font-size:12px">${esc(w.headline||'')}</div>
   <div class="k">Signals</div>${w.signals.map(s=>`<div class="sig">${s.type==='reaction'?`<b>${esc(s.reaction)}</b> on`:`💬 “${esc(s.text)}” on`} <a href="${esc(postById[s.post_id]?.url||'#')}" target="_blank">${esc(postById[s.post_id]?.author?.name||'post')}</a></div>`).join('')}
   <div class="k">Fit · score ${w.fit?.score?.toFixed(2)} · ${esc(w.tier)}</div>${dist(w.fit?.probabilities,fitLabels)}
   <div class="k">Role · ${esc(w.role?.choice)}</div>${dist(w.role?.probabilities)}
   <div class="k">Contact</div>${em?(em.status==='hit'?`<div><code>${esc(em.email)}</code></div><div style="font-size:12px;color:var(--mute);margin-top:4px">hit by <b>${esc(em.provider)}</b> · charged $${em.charged}</div>${em.verify?`<div style="font-size:12px;margin-top:4px">verified: <span class="pill ${/safe|valid/.test(em.verify.verdict)?'ok':'warn'}">${esc(em.verify.verdict)}</span> by ${esc(em.verify.provider)} · $${em.verify.charged}</div>`:''}`:`<div><span class="pill bad">${esc(em.status)}</span> ${esc(em.reason||'')}</div><div style="font-size:12px;color:var(--mute);margin-top:4px">charged $${em.charged??0}</div>`)+(em.tried?`<div style="font-size:11px;color:var(--mute);margin-top:6px">tried: ${em.tried.map(t=>`${esc(t.provider)} ${esc(t.outcome)}`).join(', ')}</div>`:''):'<div style="color:var(--mute)">not looked up (fit below threshold)</div>'}
   <div class="k">Judge</div><div style="font-size:12px">${esc(w.judge||'')}</div>`;
}
for(const id of['fTier','fRole','fEmail'])$('#'+id).onchange=renderPeople;$('#fQ').oninput=renderPeople;
renderPeople();
</script>
</body>
</html>
"""
out = ROOT / "page" / "index.html"
out.write_text(HTML.replace("__DATA__", json.dumps(run, ensure_ascii=False).replace("</", "<\\/")))
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")

const $=id=>document.getElementById(id);
const tabs=document.querySelectorAll(".tab");
const panels={analyze:$("panel-analyze"),family:$("panel-family"),history:$("panel-history")};
tabs.forEach(t=>t.addEventListener("click",()=>{tabs.forEach(x=>x.classList.remove("is-active"));t.classList.add("is-active");Object.values(panels).forEach(p=>p.classList.remove("is-active"));panels[t.dataset.tab].classList.add("is-active");if(t.dataset.tab==="family")loadFamily();if(t.dataset.tab==="history")loadHistory();}));

const msg=$("message-input"), files=$("attachments"), link=$("link-input"), fileList=$("file-list");
msg.addEventListener("input",()=>{$("char-count").textContent=msg.value.length});
files.addEventListener("change",()=>{fileList.innerHTML="";[...files.files].slice(0,5).forEach(f=>{const d=document.createElement("div");d.className="file-pill";d.textContent=`${f.type==="application/pdf"?"📄":"🖼️"} ${f.name}`;fileList.appendChild(d)})});

function state(s){$("result-empty").hidden=s!=="empty";$("result-loading").hidden=s!=="loading";$("result-error").hidden=s!=="error";$("result-content").hidden=s!=="content";}
$("analyze-form").addEventListener("submit",async e=>{
 e.preventDefault(); if(!msg.value.trim()&&!link.value.trim()&&!files.files.length)return;
 const fd=new FormData();fd.append("message",msg.value);fd.append("link",link.value);[...files.files].slice(0,5).forEach(f=>fd.append("attachments",f));
 const btn=$("analyze-btn");btn.disabled=true;btn.classList.add("is-loading");state("loading");
 try{const r=await fetch("/api/analyze",{method:"POST",body:fd});const data=await r.json();if(!r.ok){$("result-error").textContent=data.error||"Analysis failed.";state("error");return}render(data);state("content")}catch(err){$("result-error").textContent="Server se connect nahi ho pa raha. Check that Flask is running.";state("error")}finally{btn.disabled=false;btn.classList.remove("is-loading")}
});
function render(d){
 const score=Math.max(0,Math.min(100,Math.round(d.risk_score||0))), c=score>=70?"var(--danger)":score>=35?"var(--warn)":"var(--safe)";
 $("score-number").textContent=score;$("risk-label").textContent=d.risk_label||"—";$("risk-label").style.color=c;$("lang-detected").textContent=d.language_detected||"—";
 const circ=326.7, meter=$("meter-fill");meter.style.stroke=c;meter.style.strokeDashoffset=circ-(circ*score/100);
 $("alert-tag").hidden=!d.family_alerted;
 const ev=[];(d.attachments||[]).forEach(x=>ev.push(`📎 ${x}`));(d.links_found||[]).forEach(x=>ev.push(`🔗 ${x}`));$("evidence").innerHTML=ev.length?`<b>Checked:</b> ${ev.map(x=>`<span>${escapeHtml(x)}</span>`).join(" ")}`:"";
 const ul=$("flags-list");ul.innerHTML="";(d.red_flags||[]).forEach(f=>{const li=document.createElement("li");li.innerHTML=`<strong>${escapeHtml(f.phrase||"")}</strong> — ${escapeHtml(f.reason||"")}`;ul.appendChild(li)});
 $("explanation-text").textContent=d.explanation||"";$("action-text").textContent=d.suggested_action||"";
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]))}

const familyForm=$("family-form");
async function loadFamily(){const r=await fetch("/api/family");if(r.status===401)return;renderFamily(await r.json())}
function renderFamily(ms){$("family-list").innerHTML="";$("family-empty").style.display=ms.length?"none":"block";ms.forEach(m=>{const li=document.createElement("li");li.innerHTML=`<div><b>${escapeHtml(m.name)}</b><small>${escapeHtml([m.relation,m.phone].filter(Boolean).join(" · "))}</small></div>`;const b=document.createElement("button");b.className="remove-btn";b.textContent="Remove";b.onclick=async()=>{await fetch(`/api/family/${m.id}`,{method:"DELETE"});loadFamily()};li.appendChild(b);$("family-list").appendChild(li)})}
familyForm.addEventListener("submit",async e=>{e.preventDefault();const body={name:$("member-name").value.trim(),relation:$("member-relation").value.trim(),phone:$("member-phone").value.trim()};const r=await fetch("/api/family",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(r.ok){familyForm.reset();loadFamily()}else alert((await r.json()).error||"Could not add contact")});

async function loadHistory(){const box=$("history-list");box.innerHTML="<p>Loading…</p>";const r=await fetch("/api/history");const rows=await r.json();if(!rows.length){box.innerHTML="<p class='family-empty' style='display:block'>No scans yet.</p>";return}box.innerHTML=rows.map(x=>`<div class="history-card"><div><b>${escapeHtml(x.risk_label||"—")}</b><small>${new Date(x.created_at).toLocaleString()} · score ${x.risk_score}</small></div><p>${escapeHtml(x.message_snippet||"(attachment/link scan)")}</p><span>${x.attachment_names&&x.attachment_names!=="[]"?"📎 attachment":""} ${x.link?"🔗 link":""}</span></div>`).join("")}
state("empty");
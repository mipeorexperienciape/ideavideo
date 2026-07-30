'use strict';
const $ = s => document.querySelector(s);
let ME = null, MED = null, PLANS = [], VOICES = [], fmt = '16:9', authMode = 'login', pollTimer = null;

function api(path, opts = {}) {
  return fetch('/api' + path, { credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) }, ...opts })
    .then(async r => { const d = await r.json().catch(() => ({})); if (!r.ok) throw Object.assign(new Error(d.error || 'Error'), { data: d, status: r.status }); return d; });
}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
// Marca la descarga para que el servidor borre el archivo tras enviarlo (solo videos locales).
function dlUrl(u){ return (u && u.indexOf('/videos/')===0) ? u + (u.indexOf('?')>=0?'&':'?') + 'dl=1' : u; }

/* ---------- boot ---------- */
(async function boot() {
  try { const p = await api('/plans'); PLANS = p.plans; VOICES = p.voices; } catch (e) {}
  $('#voice') && ($('#voice').innerHTML = VOICES.map(v => `<option value="${v.id}" data-lang="${v.lang}">${v.label}</option>`).join(''));
  renderPlans($('#publicPlans'), false);
  await refreshMe();
  if (new URLSearchParams(location.search).get('paid')) { history.replaceState({}, '', '/'); }
})();

async function refreshMe() {
  const d = await api('/me');
  ME = d.user;
  if (ME) { showApp(d); } else { showAuth(); }
}
function showAuth() {
  $('#view-auth').classList.remove('hidden');
  $('#loginTop').classList.remove('hidden');
  ['nav','usageChip','userChip','logoutBtn'].forEach(id => $('#'+id).classList.add('hidden'));
  ['generator','videos','plans','admin'].forEach(v => $('#view-' + v).classList.add('hidden'));
}
window.scrollToAuth = (mode) => { if(mode) authTab(mode); document.getElementById('authAnchor').scrollIntoView({behavior:'smooth'}); };
function showApp(d) {
  MED = d;
  $('#view-auth').classList.add('hidden');
  $('#loginTop').classList.add('hidden');
  ['nav','userChip','logoutBtn'].forEach(id => $('#'+id).classList.remove('hidden'));
  $('#userChip').textContent = ME.email;
  $('#navAdmin').classList.toggle('hidden', !ME.is_admin);
  const q = d.usage.quota, used = d.usage.used, bonus = d.usage.bonus || 0;
  $('#usageChip').classList.remove('hidden');
  $('#usageChip').innerHTML = ME.plan === 'free'
    ? `Plan <b>Gratis</b> · demo ${d.demo_used ? 'usado' : 'disponible'}${bonus?` · ${bonus} créditos`:''}`
    : `Plan <b>${esc(d.plan.name)}</b> · ${used}/${q} este mes${bonus?` · +${bonus}`:''}`;
  const vb = $('#verifyBanner');
  if (!d.user.email_verified) {
    vb.classList.remove('hidden');
    $('#verifyLink').innerHTML = window._verifyLink
      ? `Modo prueba: abre este enlace para confirmar → <a href="${window._verifyLink}" style="color:#22c55e">${window._verifyLink}</a>`
      : 'Revisa tu correo y confirma tu cuenta.';
  } else vb.classList.add('hidden');
  go('generator');
}

/* ---------- auth ---------- */
window.authTab = (m) => { authMode = m; $('#tabLogin').classList.toggle('active', m==='login'); $('#tabReg').classList.toggle('active', m==='reg');
  $('#regFields').classList.toggle('hidden', m!=='reg'); $('#authBtn').textContent = m==='login'?'Ingresar':'Crear cuenta'; };
let _authBusy = false;
window.doAuth = async () => {
  if (_authBusy) return;                 // evita doble clic / doble envío
  _authBusy = true;
  const btn = $('#authBtn');
  btn.disabled = true;
  btn.textContent = authMode==='login' ? 'Ingresando…' : 'Creando cuenta…';
  const ref = new URLSearchParams(location.search).get('ref') || '';
  const body = { name: $('#rName').value, email: $('#aEmail').value, password: $('#aPass').value, ref };
  try {
    const r = await api(authMode==='login'?'/login':'/register', { method:'POST', body: JSON.stringify(body) });
    if (r && r.verify_link) window._verifyLink = r.verify_link;
    $('#authMsg').textContent=''; await refreshMe();
  } catch (e) {
    $('#authMsg').className='msg err';
    if (authMode==='reg' && e.status===409) {
      $('#authMsg').textContent = 'Ese correo ya está registrado. Te cambié a "Ingresar": usa tu contraseña.';
      authTab('login');
    } else {
      $('#authMsg').textContent = e.message;
    }
  } finally {
    _authBusy = false;
    btn.disabled = false;
    btn.textContent = authMode==='login' ? 'Ingresar' : 'Crear cuenta';
  }
};
window.logout = async () => { await api('/logout', { method:'POST' }); ME=null; showAuth(); };

/* ---------- nav ---------- */
window.go = (v) => {
  ['generator','videos','plans','admin'].forEach(x => $('#view-'+x).classList.add('hidden'));
  $('#view-'+v).classList.remove('hidden');
  document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('active', b.dataset.v===v));
  if (v==='videos') loadVideos();
  if (v==='plans') loadPlans();
  if (v==='admin') loadAdmin();
};
document.querySelectorAll('#nav button').forEach(b => b.onclick = () => go(b.dataset.v));
document.querySelectorAll('.segbtn').forEach(b => b.onclick = () => { document.querySelectorAll('.segbtn').forEach(x=>x.classList.remove('active')); b.classList.add('active'); fmt=b.dataset.fmt; });
function show(id, on){ $('#'+id).classList.toggle('hidden', !on); }

/* ---------- generator ---------- */
window.startJob = async () => {
  const idea = $('#idea').value.trim();
  if (idea.length < 10) { $('#genMsg').className='msg err'; $('#genMsg').textContent='Escribe tu idea con más detalle.'; return; }
  $('#genMsg').textContent=''; show('resCard',false); show('progCard',true); setProg(3,'Iniciando…');
  const body = { idea, tone:$('#tone').value, scenes:+$('#scenes').value, voice:$('#voice').value, lang:$('#lang').value, format:fmt, burn_subs:$('#subs').checked };
  try {
    const d = await api('/generate', { method:'POST', body: JSON.stringify(body) });
    poll(d.job_id);
  } catch (e) {
    show('progCard',false);
    $('#genMsg').className='msg err'; $('#genMsg').textContent = e.message;
    if (e.data && e.data.need_verify) $('#verifyBanner').classList.remove('hidden');
    else if (e.data && e.data.need_plan) setTimeout(()=>go('plans'), 1200);
  }
};
function setProg(p,m){ $('#progbar').style.width=(p||0)+'%'; $('#progmsg').textContent=m||''; }
function poll(id){
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try { const d = await api('/job/'+id);
      setProg(d.progress, d.message);
      if (d.status==='done'){ clearInterval(pollTimer); show('progCard',false); $('#player').src=d.video; $('#dl').href=dlUrl(d.video); show('resCard',true); refreshMe(); }
      else if (d.status==='error'){ clearInterval(pollTimer); show('progCard',false); $('#genMsg').className='msg err'; $('#genMsg').textContent=d.error; }
    } catch(e){}
  }, 1500);
}

/* ---------- videos ---------- */
async function loadVideos(){
  const d = await api('/videos');
  $('#videoList').innerHTML = d.videos.length ? d.videos.map(v =>
    `<div class="vitem"><div><b>${esc(v.title||'Video')}</b><div class="hint" style="margin:2px 0 0">${v.fmt} · ${v.created_at}</div></div>
     <div style="display:flex;gap:8px;align-items:center">${v.watermark?'<span class="tag wm">demo</span>':''}<a class="linkbtn" href="/videos/${v.filename}?dl=1" download>Descargar</a></div></div>`
  ).join('') : '<p class="hint">Aún no has creado videos.</p>';
}

/* ---------- plans ---------- */
function planFeatures(p){
  return (p.features || []).map(f => `<li><span class="ck">✓</span><span>${esc(f)}</span></li>`).join('');
}
function renderPlans(el, upgrade){
  if (!el) return;
  el.innerHTML = PLANS.map(p => {
    const pop = p.id==='creador';
    const price = p.price_pen === 0
      ? `<span class="amt">Gratis</span>`
      : `<span class="cur">S/</span><span class="amt">${p.price_pen}</span><span class="per">/mes</span>`;
    const usd = p.price_usd > 0
      ? `<div class="pusd">≈ US$ ${p.price_usd} / mes · cancela cuando quieras</div>`
      : `<div class="pusd">Sin tarjeta de crédito</div>`;
    let cta = '';
    if (upgrade) {
      if (p.id === 'free') {
        cta = `<button class="btn btn-ghost pbtn" disabled>Tu punto de partida</button>`;
      } else {
        const cur = ME && ME.plan === p.id;
        cta = cur
          ? `<button class="btn btn-ghost pbtn" disabled>✓ Tu plan actual</button>`
          : `<button class="btn ${pop?'btn-primary':'btn-ghost'} pbtn" onclick="checkout('${p.id}','mercadopago')">Elegir · Perú (Mercado Pago)</button>
             <button class="btn btn-ghost pbtn" style="margin-top:8px" onclick="checkout('${p.id}','stripe')">Internacional (Stripe)</button>`;
      }
    } else {
      cta = p.id === 'free'
        ? `<button class="btn btn-ghost pbtn" onclick="scrollToAuth('reg')">Empezar gratis</button>`
        : `<button class="btn ${pop?'btn-primary':'btn-ghost'} pbtn" onclick="scrollToAuth('reg')">Elegir ${esc(p.name)}</button>`;
    }
    return `<div class="plan ${pop?'pop':''}">
      ${pop?'<span class="tag">★ Más popular</span>':''}
      <div class="pn">${esc(p.name)}</div>
      <div class="ptag">${esc(p.tagline || p.desc)}</div>
      <div class="pp">${price}</div>
      ${usd}
      ${cta}
      <ul class="pfeat">${planFeatures(p)}</ul>
    </div>`;
  }).join('');
}
async function loadPlans(){
  await refreshMe();
  const d = MED;
  $('#curPlan').textContent = `Tu plan actual: ${d.plan.name}`;
  renderPlans($('#planCards'), true);
  // referidos
  $('#refLink').textContent = d.referral.link;
  $('#refCount').textContent = `Has invitado a ${d.referral.count} persona(s). Créditos disponibles: ${d.referral.bonus}.`;
  // suscripción
  const sc = $('#subCard');
  if (d.subscription && d.plan.id !== 'free') {
    sc.classList.remove('hidden');
    const st = d.subscription.status === 'canceled' ? 'Cancelada (activa hasta el fin del período)' : 'Activa';
    $('#subStatus').innerHTML = `<p>Plan <b>${esc(d.plan.name)}</b> · Estado: <b>${st}</b><br>Vence: ${d.subscription.period_end||'—'} · Vía ${d.subscription.gateway||'—'}</p>` +
      (d.subscription.status !== 'canceled' ? `<button class="btn btn-ghost" onclick="cancelSub()">Cancelar suscripción</button>` : '');
  } else sc.classList.add('hidden');
}
window.copyRef = () => { try { navigator.clipboard.writeText(MED.referral.link); } catch(e){} alert('Enlace copiado'); };
window.cancelSub = async () => { if(!confirm('¿Cancelar tu suscripción? Mantienes el acceso hasta el fin del período.'))return;
  try { const r = await api('/subscription/cancel', {method:'POST'}); alert(r.message||'Cancelada'); loadPlans(); } catch(e){ alert(e.message); } };
window.checkout = async (plan, gateway) => {
  try { const d = await api('/checkout', { method:'POST', body: JSON.stringify({ plan, gateway }) });
    location.href = d.url;
  } catch (e) { alert(e.message); }
};

/* ---------- admin ---------- */
async function loadAdmin(){
  try { const d = await api('/admin/overview');
    $('#adminKpis').innerHTML = `
      <div class="kpi"><div class="v">${d.users}</div><div class="l">Usuarios</div></div>
      <div class="kpi"><div class="v">${d.paid}</div><div class="l">De pago</div></div>
      <div class="kpi"><div class="v">${d.videos}</div><div class="l">Videos</div></div>
      <div class="kpi"><div class="v">${d.referrals}</div><div class="l">Referidos</div></div>
      <div class="kpi"><div class="v">${d.canceled}</div><div class="l">Cancelaciones</div></div>
      <div class="kpi"><div class="v" style="color:var(--accent)">S/ ${d.mrr_pen}</div><div class="l">MRR (est.)</div></div>`;
    const C = ['#7c3aed','#22c55e','#3d7bff','#eab308','#ef4444'];
    barChart($('#chUsers'), d.users_by_day.map(x=>x.c), d.users_by_day.map(x=>x.d.slice(5)), '#7c3aed');
    barChart($('#chVideos'), d.videos_by_day.map(x=>x.c), d.videos_by_day.map(x=>x.d.slice(5)), '#22c55e');
    const pk = Object.keys(d.by_plan), pv = pk.map(k=>d.by_plan[k]);
    donut($('#chPlans'), pv, C);
    $('#chPlansLeg').innerHTML = pk.map((k,i)=>`<span><span class="dotm" style="background:${C[i%C.length]}"></span>${k} (${pv[i]})</span>`).join('');
  } catch(e){ $('#adminKpis').innerHTML = `<p class="hint">${esc(e.message)}</p>`; }
}
window.runExpiry = async () => { try { const r = await api('/admin/run-expiry-warnings',{method:'POST'}); $('#expMsg').textContent = `Avisos enviados: ${r.notified}`; } catch(e){ $('#expMsg').textContent = e.message; } };

/* ---------- charts (SVG) ---------- */
function barChart(el, vals, labels, color){
  if(!el) return; const w=Math.max(el.clientWidth||500,300), h=170, pad=26, max=Math.max(...vals,1)*1.15, bw=(w-pad*2)/Math.max(vals.length,1);
  let g=''; for(let i=0;i<4;i++){const y=pad+(h-pad*1.5)*i/3; g+=`<line x1="${pad}" y1="${y}" x2="${w-4}" y2="${y}" stroke="#2a3048"/>`;}
  let b=''; vals.forEach((v,i)=>{const bh=(v/max)*(h-pad*1.6),x=pad+i*bw+bw*0.2,y=(h-pad*0.6)-bh;
    b+=`<rect x="${x}" y="${y}" width="${bw*0.6}" height="${bh}" rx="4" fill="${color}"><title>${labels[i]}: ${v}</title></rect>`;
    if(vals.length<=12||i%2===0)b+=`<text x="${x+bw*0.3}" y="${h-6}" fill="#8b8fa3" font-size="10" text-anchor="middle">${labels[i]||''}</text>`;});
  el.innerHTML=`<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}">${g}${b}</svg>`;
}
function donut(el, parts, colors){
  if(!el) return; const size=150,total=parts.reduce((a,b)=>a+b,0)||1,r=size/2-14,cx=size/2,cy=size/2; let a=-Math.PI/2,seg='';
  parts.forEach((p,i)=>{const ang=p/total*Math.PI*2,x1=cx+r*Math.cos(a),y1=cy+r*Math.sin(a);a+=ang;const x2=cx+r*Math.cos(a),y2=cy+r*Math.sin(a),lg=ang>Math.PI?1:0;
    seg+=`<path d="M${cx} ${cy} L${x1} ${y1} A${r} ${r} 0 ${lg} 1 ${x2} ${y2} Z" fill="${colors[i%colors.length]}" stroke="#171331" stroke-width="2"/>`;});
  el.innerHTML=`<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">${seg}<circle cx="${cx}" cy="${cy}" r="${r*0.58}" fill="#171331"/><text x="${cx}" y="${cy+5}" text-anchor="middle" font-size="18" font-weight="800" fill="#fff">${total}</text></svg>`;
}

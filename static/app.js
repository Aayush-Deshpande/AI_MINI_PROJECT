'use strict';
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = p => new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(p/100);
let user=null, view='discover', catalog={destinations:[],tours:[]}, admin=null, register=false, noticeTimer;
let filters={search:'',category:'',budget:''};
let currentPlan=null;
async function api(path, method='GET', body) {
  const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-STMS-Request':'1'},...(body?{body:JSON.stringify(body)}:{})});
  const data=await r.json(); if(!r.ok) throw new Error(data.error||'Request failed'); return data;
}
function notify(text,error=false){const n=$('#notice');n.textContent=text;n.className='notice'+(error?' error':'');n.hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>n.hidden=true,6000);}
function opts(list,value='id',label='name'){return list.map(x=>`<option value="${esc(x[value])}">${esc(x[label])}</option>`).join('');}
function empty(text){return `<div class="empty">${esc(text)}</div>`;}
function account(){
  $('#account').innerHTML=user?`<span>${esc(user.name)} · ${esc(user.role)}</span><button class="secondary small" id="logout">Sign out</button>`:'<button id="login">Sign in ↗</button>';
  $('#ops-nav').hidden=!user||user.role==='tourist';
  if(user) $('#logout').onclick=async()=>{try{await api('/logout','POST');user=null;currentPlan=null;view='discover';await render();}catch(e){notify(e.message,true);}};
  else $('#login').onclick=()=>$('#auth').showModal();
}
async function render(){
  account(); document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  try {
    catalog=await api('/catalog');
    if(view==='discover') await discover();
    else if(view==='reviews') await reviews();
    else if(view==='planner') await planner();
    else if(!user) $('#main').innerHTML=`<h1 class="page-title">Make room for your next trip.</h1>${empty('Sign in to manage your travel, reservations and support requests.')}<p><button id="page-login">Sign in to continue</button></p>`;
    else if(view==='trips') await trips();
    else if(view==='support') await support();
    else if(view==='operations') await operations();
    if($('#page-login')) $('#page-login').onclick=()=>$('#auth').showModal();
    bindForms();
  }catch(e){notify(e.message,true);$('#main').innerHTML=empty('Unable to load this view. Please try again.');}
}
async function planner(){
  const config=await api('/ai/config');
  const start=new Date();const localDate=[start.getFullYear(),String(start.getMonth()+1).padStart(2,'0'),String(start.getDate()).padStart(2,'0')].join('-');
  $('#main').innerHTML=`<p class="eyebrow">A LITTLE INSPIRATION, MADE FOR YOU</p><h1 class="page-title">Your next trip starts with a spark. ✦</h1><p class="muted">Turn your interests into a day-by-day plan, grounded in the Wanderly catalog.</p><div class="split"><section class="panel"><span class="tag">${config.configured?'NVIDIA NIM connected':'Catalog preview · AI key not configured'}</span><h2 class="planner-heading">Tell us your travel style</h2><p class="note">${config.configured?'Your preferences and public destination details are sent to NVIDIA to generate the plan. Avoid entering private information.':'A fixed preview is available now. Configure NVIDIA_API_KEY on the server to enable personalised AI generation.'} Plans are suggestions; confirm details with your guide.</p><form id="planner-form"><label>Where would you like to explore?<select name="destination_id">${opts(catalog.destinations)}</select></label><div class="inline"><label>Start date<input type="date" name="start_date" value="${localDate}" min="${localDate}" required></label><label>Days<input name="days" type="number" value="3" min="1" max="7" required></label></div><div class="inline"><label>Planning budget (₹)<input name="budget" type="number" value="10000" min="1" max="1000000" required></label><label>Travellers<input name="guests" type="number" value="2" min="1" max="20" required></label></div><label>What do you enjoy?<textarea name="interests" maxlength="500" placeholder="Quiet walks, local food, architecture, a relaxed pace…" required>Local culture, scenic walks and a relaxed pace</textarea></label><button ${user?.role==='tourist'?'':'type="button"'} id="generate-plan">${!user?'Sign in to plan':user.role!=='tourist'?'Use a tourist account':config.configured?'Generate my trip ✦':'Try the catalog preview'}</button><p class="muted planner-disclaimer">No reservations are created automatically. Food, lodging and transport costs are not quoted.</p><p id="planner-error" role="alert"></p></form></section><section id="plan-output" class="panel">${planHTML()}</section></div>`;
  if(!user){$('#generate-plan').onclick=()=>$('#auth').showModal();return;}
  if(user.role!=='tourist'){$('#generate-plan').disabled=true;return;}
  $('#planner-form').onsubmit=async e=>{
    e.preventDefault();const b=$('#generate-plan');b.disabled=true;b.textContent=config.configured?'Creating your itinerary…':'Preparing preview…';$('#planner-error').textContent='';
    try{const d=Object.fromEntries(new FormData(e.target));for(const k of ['destination_id','days','budget','guests'])d[k]=+d[k];currentPlan=await api('/ai/plan','POST',d);$('#plan-output').innerHTML=planHTML();bindSavePlan();notify(currentPlan.plan.mode==='ai'?'Your AI itinerary is ready.':'Your catalog preview is ready.');}
    catch(err){$('#planner-error').textContent=err.message;}
    finally{b.disabled=false;b.textContent=config.configured?'Generate my trip ✦':'Try the catalog preview';}
  };
  bindSavePlan();
}
function planHTML(){
  if(!currentPlan)return `<p class="eyebrow">YOUR PERSONALISED JOURNEY</p><h2>Space for your next story.</h2>${empty('Choose a destination and tell us what you enjoy. Your plan will appear here.')}<p class="note">Save a generated plan to My trips when you are happy with it. You can book available departures from Discover.</p>`;
  const p=currentPlan.plan;
  return `<span class="tag">${p.mode==='ai'?'✦ Generated with NVIDIA NIM':'Fixed preview · not AI generated'}</span><h2 class="planner-heading">${esc(p.title)}</h2><p class="muted">${esc(p.summary)}</p>${p.days.map(d=>`<article class="record plan-day"><span class="tag">DAY ${d.day} · ${esc(d.date)}</span><h3>${esc(d.title)}</h3><p class="muted">${esc(d.destination)} · ${esc(d.city)}</p>${['morning','afternoon','evening'].map(k=>`<p><strong>${k[0].toUpperCase()+k.slice(1)}</strong><br>${esc(d[k])}</p>`).join('')}<p class="note">${esc(d.notes)}</p></article>`).join('')}<h3>Bring along</h3><p>${p.packing.map(esc).join(' · ')}</p><button id="save-plan">Save to my itinerary</button><p class="planner-disclaimer muted">Saving adds personal itinerary items. Book tours separately in Discover.</p>`;
}
function bindSavePlan(){if($('#save-plan'))$('#save-plan').onclick=async()=>{const b=$('#save-plan');b.disabled=true;try{const r=await api(`/ai/plans/${currentPlan.id}/save`,'POST',{});notify(r.message);b.textContent='Saved to My trips';}catch(e){notify(e.message,true);b.disabled=false;}};}
async function discover(){
  const categories=[...new Set(catalog.destinations.map(d=>d.category))];
  const data=await api('/catalog?'+new URLSearchParams(filters));
  $('#main').innerHTML=`<section class="hero"><div class="hero-copy"><p class="eyebrow">GO SOMEWHERE THAT STAYS WITH YOU</p><h1>Less ordinary.<br>More <em>discovery.</em></h1><p>Find local experiences, meet knowledgeable guides, and bring your next journey together.</p><button id="explore">Explore experiences ↓</button></div><div class="hero-art" role="img" aria-label="Illustration of green mountains beneath a golden sun"><div class="sun"></div><div class="mountain"></div><div class="mountain two"></div><div class="mountain three"></div><div class="art-caption">A NEW PERSPECTIVE AWAITS<strong>Your next story starts here.</strong></div></div></section>
  <form id="filter-form" class="filters"><label>Where would you like to go?<input name="search" placeholder="Search destinations or cities" value="${esc(filters.search)}"></label><label>Your kind of adventure<select name="category"><option value="">All experiences</option>${categories.map(c=>`<option ${filters.category===c?'selected':''}>${esc(c)}</option>`).join('')}</select></label><label>Budget per person (₹)<input name="budget" type="number" min="0" step="1" placeholder="Any budget" value="${esc(filters.budget)}"></label><button>Find my escape</button></form>
  <div class="section-heading" id="experiences"><div><p class="eyebrow">CURATED FOR THE CURIOUS</p><h2>Find your next favourite place</h2><p>Rule-based picks filtered by your interests and budget, sorted by guest rating.</p></div><span class="tag">${data.destinations.length} destinations to discover</span></div><div class="grid">${data.destinations.map(d=>{
    const tours=data.tours.filter(t=>t.destination_id===d.id);
    return `<article class="card"><div class="card-art art-${esc(d.category)}"><span class="tag">${esc(d.category)}</span><span class="city-art">${esc(d.city)}</span></div><div class="card-body"><h3>${esc(d.name)}</h3><p>${esc(d.description)}</p><span class="muted">${d.rating?'★ '+esc(d.rating)+' / 5':'New • Be the first to explore'}</span>${tours.length?`<form class="tour-form" data-form="book"><label>Departure · price per person · seats available<select name="tour_id">${tours.map(t=>`<option value="${t.id}" ${t.available===0?'disabled':''}>${esc(t.date)} · ${money(t.price_paise)} · ${t.available} left</option>`).join('')}</select></label><div class="tour-bottom"><label>Guests<input name="seats" type="number" value="1" min="1" max="20" required></label><button ${tours.every(t=>t.available===0)?'disabled':''}>Request booking ↗</button></div></form>`:'<p>No upcoming departures.</p>'}</div></article>`;
  }).join('')}</div>${data.destinations.length?'':empty('No matches. Try another search or a higher budget.')}`;
  $('#explore').onclick=()=>$('#experiences').scrollIntoView({behavior:'smooth'});
  $('#filter-form').onsubmit=async e=>{e.preventDefault();filters=Object.fromEntries(new FormData(e.target));if(!filters.budget) filters.budget='0';await render();};
}
function bookingList(bookings){return bookings.length?bookings.map(b=>`<article class="record"><span class="status ${esc(b.status)}">${esc(b.status)}</span><h3>${esc(b.destination)}</h3><p>${esc(b.date)} · ${b.seats} guest(s) · ${money(b.total)}<br>Reservation #${b.id} · ${esc(b.tourist)}</p><div class="record-actions">${user.role==='tourist'&&['pending','confirmed'].includes(b.status)?`<button class="secondary small" data-booking="${b.id}" data-status="cancelled">Cancel reservation</button>`:''}${user.role!=='tourist'&&b.status==='pending'?`<button class="small" data-booking="${b.id}" data-status="confirmed">Confirm</button>`:''}${user.role!=='tourist'&&b.status==='confirmed'?`<button class="small" data-booking="${b.id}" data-status="completed">Mark completed</button>`:''}${user.role==='admin'&&['pending','confirmed'].includes(b.status)?`<button class="secondary small" data-booking="${b.id}" data-status="cancelled">Cancel</button>`:''}</div></article>`).join(''):empty('No reservations yet. Your next adventure is waiting.');}
async function trips(){
  if(user.role!=='tourist'){$('#main').innerHTML=empty('Tourists manage personal trips here. Use Operations to manage assigned reservations.');return;}
  const [bookings,items]=await Promise.all([api('/bookings'),api('/itinerary')]);
  $('#main').innerHTML=`<p class="eyebrow">EVERY DETAIL, TOGETHER</p><h1 class="page-title">Your journey, your way.</h1><p class="muted">Reservations and a personal plan for the days ahead.</p><div class="split"><section class="panel"><h2>My reservations</h2><p class="note">Reservations start pending until a guide confirms. No payment is collected. Cancellation is available before departure.</p>${bookingList(bookings.bookings)}</section><section><div class="panel"><h2>Build your itinerary</h2><form data-form="itinerary"><label>Destination<select name="destination_id">${opts(catalog.destinations)}</select></label><div class="inline"><label>Date<input name="date" type="date" required></label><label>Title<input name="title" placeholder="Morning in the old town" maxlength="100" required></label></div><label>Notes<textarea name="notes" maxlength="2000" placeholder="Places to visit, things to remember…"></textarea></label><button>Add to my plan</button></form></div><div class="panel"><h2>Your itinerary</h2>${items.items.length?items.items.map(i=>`<article class="record"><span class="tag">${esc(i.date)}</span><h3>${esc(i.title)}</h3><p>${esc(i.destination)}<br>${esc(i.notes)}</p><button class="secondary small" data-delete="${i.id}">Remove</button></article>`).join(''):empty('Add your first stop above.')}</div></section></div>`;
}
async function reviews(){
  const data=await api('/reviews');
  $('#main').innerHTML=`<p class="eyebrow">FROM PEOPLE WHO HAVE BEEN THERE</p><h1 class="page-title">Stories worth sharing.</h1><p class="muted">Verified reviews from tourists who completed their tours.</p><div class="split"><section class="panel"><h2>Traveller reviews</h2>${data.reviews.length?data.reviews.map(r=>`<article class="record"><span class="tag">${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</span><h3>${esc(r.destination)}</h3><p>${esc(r.comment)}</p><small class="muted">${esc(r.author)} · Verified traveller</small></article>`).join(''):empty('No reviews yet. Completed journeys unlock the first stories.')}</section><section class="panel"><h2>Share your experience</h2><p class="note">Complete a booked tour before reviewing its destination. A new submission updates your existing review.</p>${user?.role==='tourist'?`<form data-form="review"><label>Destination<select name="destination_id">${opts(catalog.destinations)}</select></label><label>Rating<select name="rating"><option value="5">5 — Excellent</option><option value="4">4 — Very good</option><option value="3">3 — Good</option><option value="2">2 — Fair</option><option value="1">1 — Poor</option></select></label><label>Your review<textarea name="comment" maxlength="1000" required></textarea></label><button>Publish review</button></form>`:empty('Sign in as a tourist to write a review.')}</section></div>`;
}
async function support(){
  const data=await api('/tickets');
  $('#main').innerHTML=`<p class="eyebrow">A HELPING HAND</p><h1 class="page-title">How can we help?</h1><p class="note">For booking and application questions. This inbox is not monitored for emergencies; contact local emergency services when needed.</p><div class="split"><section class="panel"><h2>Send a request</h2><form data-form="ticket"><label>Subject<input name="subject" maxlength="150" required></label><label>Tell us more<textarea name="message" maxlength="3000" required></textarea></label><button>Submit request</button></form></section><section class="panel"><h2>${user.role==='admin'?'All requests':'Your requests'}</h2>${data.tickets.length?data.tickets.map(t=>`<article class="record"><span class="status">${esc(t.status)}</span><h3>${esc(t.subject)}</h3><p>${esc(t.message)}</p><small>${esc(t.author)} · #${t.id}</small>${t.response?`<p class="note">Response: ${esc(t.response)}</p>`:''}${user.role==='admin'?`<form data-form="resolve" data-id="${t.id}"><label>Administrator response<textarea name="response" maxlength="3000" required>${esc(t.response)}</textarea></label><button class="small">Save & resolve</button></form>`:''}</article>`).join(''):empty('No support requests.')}</section></div>`;
}
async function operations(){
  if(user.role==='tourist'){$('#main').innerHTML=empty('Operations is available to guides and administrators.');return;}
  const bookings=await api('/bookings');
  let html=`<p class="eyebrow">${user.role==='admin'?'ADMINISTRATION':'GUIDE WORKSPACE'}</p><h1 class="page-title">Make every journey count.</h1>`;
  if(user.role==='admin'){
    admin=await api('/admin');const r=admin.report;
    html+=`<div class="stats"><div class="stat"><strong>${r.users}</strong><span>Registered users</span></div><div class="stat"><strong>${r.destinations}</strong><span>Destinations</span></div><div class="stat"><strong>${r.bookings}</strong><span>Reservations</span></div><div class="stat"><strong>${money(r.reserved_value)}</strong><span>Reserved value · not revenue</span></div></div><p class="muted">${r.by_status.map(s=>`${esc(s.status)}: ${s.count}`).join(' · ')||'No booking activity yet'}</p><div class="split"><section class="panel"><h2>Destination editor</h2><label>Choose a record<select id="edit-destination"><option value="">Create new destination</option>${opts(admin.destinations)}</select></label><form data-form="destination" id="destination-form"><input name="id" type="hidden"><div class="inline"><label>Name<input name="name" maxlength="100" required></label><label>City<input name="city" maxlength="100" required></label></div><label>Category<input name="category" maxlength="40" placeholder="Heritage, Nature, Adventure…" required></label><label>Description<textarea name="description" maxlength="2000" required></textarea></label><label>Visibility<select name="active"><option value="1">Active</option><option value="0">Inactive</option></select></label><button>Save destination</button></form></section><section class="panel"><h2>Schedule a guided tour</h2><form data-form="tour"><label>Destination<select name="destination_id">${opts(admin.destinations.filter(d=>d.active))}</select></label><label>Assigned guide<select name="guide_id">${opts(admin.guides)}</select></label><label>Departure date<input name="date" type="date" required></label><div class="inline"><label>Price per guest (₹)<input name="price" type="number" min="0.01" max="1000000" step="0.01" required></label><label>Capacity<input name="capacity" type="number" min="1" max="200" value="12" required></label></div><button>Create departure</button></form></section></div>`;
  }
  html+=`<section class="panel"><h2>${user.role==='admin'?'All reservations':'Assigned reservations'}</h2><p class="note">Confirm pending reservations. Mark a confirmed reservation completed on or after its departure date.</p>${bookingList(bookings.bookings)}</section>`;
  if(admin&&user.role==='admin') html+=`<details class="panel"><summary>Recent audit trail</summary>${admin.audit.map(a=>`<p>#${a.id} · ${esc(a.created)} UTC · actor ${a.actor} · ${esc(a.action)} · record ${a.target}</p>`).join('')||'No events yet.'}</details>`;
  $('#main').innerHTML=html;
  if($('#edit-destination')) $('#edit-destination').onchange=e=>{const d=admin.destinations.find(d=>d.id===Number(e.target.value));const f=$('#destination-form');f.reset();if(d)Object.keys(d).forEach(k=>{if(f.elements[k])f.elements[k].value=d[k];});else f.elements.id.value='';};
}
function bindForms(){
  document.querySelectorAll('form[data-form]').forEach(form=>form.onsubmit=async e=>{
    e.preventDefault();if(!user){$('#auth').showModal();return;}
    const button=form.querySelector('button');button.disabled=true;
    const d=Object.fromEntries(new FormData(form));let path;
    try{
      switch(form.dataset.form){
        case 'book': path='/bookings';d.tour_id=+d.tour_id;d.seats=+d.seats;d.request_key=form.dataset.key||(form.dataset.key=crypto.randomUUID());break;
        case 'itinerary':path='/itinerary';d.destination_id=+d.destination_id;break;
        case 'review':path='/reviews';d.destination_id=+d.destination_id;d.rating=+d.rating;break;
        case 'ticket':path='/tickets';break;
        case 'resolve':path=`/tickets/${form.dataset.id}/resolve`;break;
        case 'destination':path='/admin/destinations';d.active=+d.active;if(d.id)d.id=+d.id;else delete d.id;break;
        case 'tour':path='/admin/tours';d.destination_id=+d.destination_id;d.guide_id=+d.guide_id;d.capacity=+d.capacity;d.price_paise=Math.round(Number(d.price)*100);delete d.price;break;
      }
      const result=await api(path,'POST',d);notify(result.message);await render();
    }catch(e){notify(e.message,true);button.disabled=false;}
  });
  document.querySelectorAll('[data-booking]').forEach(b=>b.onclick=async()=>{if(b.dataset.status==='cancelled'&&!confirm('Cancel this reservation and release its seats?'))return;try{const r=await api(`/bookings/${b.dataset.booking}/status`,'POST',{status:b.dataset.status});notify(r.message);await render();}catch(e){notify(e.message,true);}});
  document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=async()=>{try{await api('/itinerary/'+b.dataset.delete,'DELETE');notify('Itinerary item removed');await render();}catch(e){notify(e.message,true);}});
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;render();});
document.querySelectorAll('.brand').forEach(b=>b.onclick=e=>{e.preventDefault();view='discover';render();});
$('#close-auth').onclick=()=>$('#auth').close();
$('#toggle-auth').onclick=()=>{register=!register;$('#name-label').hidden=!register;$('#auth-form').elements.name.required=register;$('#auth-title').textContent=register?'Start your next story.':'Welcome back.';$('#auth-submit').textContent=register?'Create account':'Sign in';$('#toggle-auth').textContent=register?'Already have an account? Sign in':'Create an account';$('#auth-error').textContent='';};
$('#auth-form').onsubmit=async e=>{e.preventDefault();$('#auth-submit').disabled=true;$('#auth-error').textContent='';try{const data=Object.fromEntries(new FormData(e.target));if(register)await api('/register','POST',data);await api('/login','POST',data);user=(await api('/me')).user;$('#auth').close();e.target.reset();notify('Welcome, '+user.name);await render();}catch(err){$('#auth-error').textContent=err.message;}finally{$('#auth-submit').disabled=false;}};
(async()=>{try{const session=await api('/me');user=session.user;const demo=document.querySelector('#auth details');if(demo)demo.hidden=!session.demo;await render();}catch(e){notify(e.message,true);}})();

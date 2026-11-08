document.addEventListener('click', e => {
 const digit=e.target.closest('[data-digit]');
 if(digit){
  const input=document.querySelector('#kg'), key=digit.dataset.digit;
  // Keep the decimal separator between taps; number inputs normalise trailing dots.
  let value=input.dataset.keypadValue ?? input.value;
  if(key==='clear')value=value.slice(0,-1)||'0';
  else if(key==='.'&&!value.includes('.'))value+='.';
  else if(key!=='.'&&(!value.includes('.')||value.split('.')[1].length<1))value=(value==='0'?'':value)+key;
  if(Number(value)<=Number(input.max)){
   input.dataset.keypadValue=value;
   input.value=value.endsWith('.')?value.slice(0,-1):value;
   input.dispatchEvent(new Event('change',{bubbles:true}));
  }
 }
 const step=e.target.closest('[data-step]');if(step){const input=step.parentElement.querySelector('input');input.value=Math.max(0,Math.min(9999,Number(input.value)+Number(step.dataset.step)));input.dispatchEvent(new Event('change',{bubbles:true}));}
 if(e.target.closest('[data-print]')){e.target.closest('.stub-wrap').querySelector('[role=status]').textContent='Opening print dialog…';window.print();}
});
document.addEventListener('input',e=>{if(e.target.id==='kg')delete e.target.dataset.keypadValue;});
// HTMX prices only; final creation is a normal POST with the same server rules.
document.addEventListener('submit',e=>{if(e.target.id==='intake'){e.stopPropagation();}},true);
document.addEventListener('htmx:configRequest',e=>{const token=document.querySelector('[name=csrfmiddlewaretoken]');if(token)e.detail.headers['X-CSRFToken']=token.value;});

document.addEventListener('click',e=>{const create=e.target.closest('[data-create]');if(create){e.preventDefault();const f=create.form;if(f.reportValidity())f.requestSubmit();}});

// Contextual clock and actual browser connectivity; no simulated replication state.
function updateClock(){
 const now=new Date();
 document.querySelectorAll('[data-clock]').forEach(el=>{
  el.dateTime=now.toISOString();
  el.textContent=new Intl.DateTimeFormat('en-PH',{timeZone:'Asia/Manila',weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(now);
 });
}
updateClock();setInterval(updateClock,30000);
function updateConnection(){
 document.querySelectorAll('[data-connection]').forEach(el=>{
  el.classList.toggle('off',!navigator.onLine);
  el.querySelector('[data-connection-label]').textContent=el.dataset.servingHub==='true'?(navigator.onLine?'Connected to hub':'Disconnected'):(navigator.onLine?'Online':'Offline');
 });
}
updateConnection();window.addEventListener('online',updateConnection);window.addEventListener('offline',updateConnection);
function updateIntake(){
 const form=document.querySelector('#intake');if(!form)return;
 const kg=Number(form.querySelector('#kg').value);
 const hasPieces=[...form.querySelectorAll('[name^="piece_"]')].some(e=>Number(e.value)>0);
 form.querySelector('[data-create]').disabled=!(kg>0||hasPieces);
 const hint=form.querySelector('[data-load-hint]');
 if(hint){
  const service=form.querySelector('[name=service]:checked');
  const isLoad=service&&service.closest('label').textContent.includes('/load');
  hint.textContent=isLoad&&kg>0?Math.ceil(kg/Number(hint.dataset.kilos))+' load(s) · '+hint.dataset.kilos+' kg per load':'';
 }
 const existing=form.querySelector('[name=customer]:checked');
 const name=existing?.dataset.customerLabel||form.querySelector('[name=customer_name]').value.trim()||'Walk-in';
 form.querySelector('[data-summary-customer]').textContent=name;
 const selected=form.querySelector('[data-customer-selected]');
 selected.hidden=!existing;
 if(existing)form.querySelector('[data-customer-name]').textContent=name;
}
updateIntake();document.addEventListener('input',updateIntake);document.addEventListener('change',updateIntake);
document.addEventListener('click',e=>{
 if(e.target.closest('[data-walkin]')){
  const form=document.querySelector('#intake');
  form.querySelectorAll('[name=customer]').forEach(el=>{el.checked=false;});
  ['customer_search','customer_name','customer_phone'].forEach(name=>{form.querySelector('[name='+name+']').value='';});
  document.querySelector('#customers').replaceChildren();updateIntake();
 }
});

// Dialog actions use the same server forms, validation, CSRF and action-bound PIN guard.
let appDialog,dialogTrigger,dialogRequest=0,actionPending=false;
function closeAppDialog(){if(!actionPending&&appDialog?.open)appDialog.close();}
function showAppDialog(doc,url,trigger){
 const content=doc.querySelector('main .stub-wrap,main .auth-card');
 if(!content)return false;
 if(!appDialog){
  appDialog=document.createElement('dialog');appDialog.className='app-dialog';
  const close=document.createElement('button');close.className='x dialog-close';close.type='button';close.setAttribute('aria-label','Close dialog');close.textContent='×';close.addEventListener('click',closeAppDialog);
  appDialog.append(close);document.body.append(appDialog);
  appDialog.addEventListener('cancel',event=>{if(actionPending)event.preventDefault();});
  appDialog.addEventListener('click',event=>{if(event.target===appDialog){const box=appDialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)closeAppDialog();}});
  appDialog.addEventListener('close',()=>{if(appDialog.open)return;++dialogRequest;appDialog.querySelector('.dialog-content')?.remove();if(dialogTrigger?.isConnected)dialogTrigger.focus();});
 }
 appDialog.querySelector('.dialog-content')?.remove();
 content.classList.add('dialog-content');
 content.querySelectorAll('form:not([action])').forEach(form=>form.action=url);
 const ids=new Map();
 content.querySelectorAll('[id]').forEach(el=>{const old=el.id;el.id='dialog-'+old;ids.set(old,el.id);});
 content.querySelectorAll('[for],[aria-controls],[aria-labelledby]').forEach(el=>['for','aria-controls','aria-labelledby'].forEach(attr=>{if(el.hasAttribute(attr))el.setAttribute(attr,el.getAttribute(attr).split(' ').map(id=>ids.get(id)||id).join(' '));}));
 const heading=content.querySelector('h2');
 if(heading){heading.id='app-dialog-title';appDialog.setAttribute('aria-labelledby',heading.id);}
 appDialog.append(content);if(trigger)dialogTrigger=trigger;
 if(!appDialog.open)appDialog.showModal();
 (content.querySelector('[autofocus]')||appDialog.querySelector('.dialog-close')).focus();
 return true;
}
function parsePage(html){return new DOMParser().parseFromString(html,'text/html');}
document.addEventListener('click',async e=>{
 if(e.target.closest('[data-dialog-cancel]')?.closest('dialog')){e.preventDefault();closeAppDialog();return;}
 const link=e.target.closest('a[data-dialog]');
 if(!link||e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||actionPending)return;
 const url=new URL(link.href,location.href);if(url.origin!==location.origin)return;
 e.preventDefault();const sequence=++dialogRequest;
 try{
  const response=await fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}});
  const doc=parsePage(await response.text());
  if(sequence!==dialogRequest)return;
  if(!response.ok||response.redirected||!showAppDialog(doc,response.url,link))location.assign(response.url||url);
 }catch(error){location.assign(url);}
});
function refreshMain(doc){
 const main=doc.querySelector('main'),current=document.querySelector('main');
 if(!main||!current)throw new Error('Could not refresh this screen.');
 const focusHref=dialogTrigger?.getAttribute('href');
 current.replaceChildren(...main.childNodes);
 const rail=doc.querySelector('.rail'),currentRail=document.querySelector('.rail');
 if(rail&&currentRail)currentRail.replaceChildren(...rail.childNodes);
 window.htmx?.process(current);updateIntake();updateClock();
 if(dialogTrigger&&!dialogTrigger.isConnected){
  dialogTrigger=[...current.querySelectorAll('a[href]')].find(link=>link.getAttribute('href')===focusHref)||current.querySelector('[data-create],h2');
  if(dialogTrigger?.matches('h2'))dialogTrigger.tabIndex=-1;
  dialogTrigger?.focus({preventScroll:true});
 }
}
document.addEventListener('submit',async e=>{
 const form=e.target;
 if(!form.matches('[data-action-dialog]')&&!form.closest('.app-dialog'))return;
 e.preventDefault();e.stopImmediatePropagation();
 if(actionPending||!form.reportValidity())return;
 actionPending=true;
 const data=new FormData(form);if(e.submitter?.name)data.append(e.submitter.name,e.submitter.value);
 const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
 const trigger=appDialog?.open?null:e.submitter;
 try{
  const response=await fetch(form.action,{method:'POST',body:data,headers:{'X-Requested-With':'XMLHttpRequest'}});
  const doc=parsePage(await response.text());
  if(!response.redirected){
   if(!showAppDialog(doc,response.url,trigger)){
    if(doc.querySelector('#intake')){appDialog?.close();refreshMain(doc);}
    else throw new Error('Could not complete the action. Please try again.');
   }
  }else{
   // Refresh the original screen without changing its URL, filters or scroll position.
   const screen=await fetch(location.href,{headers:{'X-Requested-With':'XMLHttpRequest'}});
   if(!screen.ok||screen.redirected){location.assign(screen.url);return;}
   const updated=parsePage(await screen.text());
   // Redirects consume Django messages, so keep the action's feedback and Undo.
   updated.querySelectorAll('main .toast').forEach(el=>el.remove());
   doc.querySelectorAll('main .toast').forEach(el=>updated.querySelector('main').prepend(el));
   appDialog?.close();refreshMain(updated);
   if(form.id==='intake'||(form.matches('[data-pin-form]')&&document.querySelector('#intake'))){showAppDialog(doc,response.url,document.querySelector('[data-create]'));}
  }
 }catch(error){
  let status=form.querySelector('[data-action-error]');
  if(!status){status=document.createElement('p');status.className='error';status.dataset.actionError='';status.setAttribute('role','alert');form.append(status);}
  status.textContent='The action could not be confirmed. Check the current screen before trying again.';
 }finally{actionPending=false;buttons.forEach(b=>b.disabled=false);}
},true);
document.addEventListener('click',e=>{
 const key=e.target.closest('[data-pin]');if(!key)return;
 const form=key.closest('form'),input=form.querySelector('[name=pin]');
 if(actionPending)return;
 if(key.dataset.pin==='clear')input.value='';
 else if(key.dataset.pin==='back')input.value=input.value.slice(0,-1);
 else if(input.value.length<4)input.value+=key.dataset.pin;
 input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();
});
document.addEventListener('input',e=>{
 if(!e.target.matches('[data-pin-form] [name=pin]'))return;
 e.target.value=e.target.value.replace(/\D/g,'').slice(0,4);
 e.target.closest('label').querySelectorAll('.pin-dots i').forEach((dot,i)=>dot.classList.toggle('on',i<e.target.value.length));
 if(e.target.value.length===4&&!actionPending)e.target.form.requestSubmit();
});
document.addEventListener('change',e=>{
 if(e.target.name==='paper_release')e.target.setAttribute('aria-expanded',String(e.target.checked));
});
// Keep auto-refresh from replacing an action's focus target while a dialog is open.
document.addEventListener('htmx:beforeRequest',e=>{if(appDialog?.open&&e.detail.elt.matches('#board,#machine-grid'))e.preventDefault();});

// Preview stock-count variance; the server recomputes it when the count is saved.
document.addEventListener('input',e=>{
 if(!e.target.matches('[data-count-input]'))return;
 const input=e.target,output=input.closest('tr').querySelector('[data-count-variance]');
 const difference=Number(input.value)-Number(input.dataset.expected);
 const valid=input.value!==''&&Number.isFinite(difference)&&input.validity.valid;
 output.textContent=valid?(difference>0?'+':'')+Number(difference.toFixed(3)):'—';
 output.className='pill '+(!valid||Math.abs(difference)<1?'plain':Math.abs(difference)>3?'crit':'warn');
});

// Inline catalog edits keep ordinary Save buttons as a no-JavaScript fallback.
document.addEventListener('change',e=>{
 const form=e.target.form;
 if(form?.matches('[data-catalog-save]'))form.requestSubmit();
});
document.addEventListener('submit',async e=>{
 const form=e.target;
 if(!form.matches('[data-catalog-save]'))return;
 e.preventDefault();
 if(!form.reportValidity())return;
 if(form.dataset.saving){form.dataset.pending='1';return;}
 form.dataset.saving='1';
 const status=form.querySelector('[role="status"]');status.textContent='Saving…';
 try{
  const response=await fetch(form.action,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}});
  if(response.redirected)throw new Error('Your session changed. Reload the page before saving.');
  const result=await response.json();
  if(!response.ok)throw new Error(Object.values(result.errors||{}).flat().join(' ')||'Could not save. Try again.');
  status.textContent='Saved';
 }catch(error){status.textContent=error.message||'Could not save. Try again.';}
 finally{
  delete form.dataset.saving;
  if(form.dataset.pending){delete form.dataset.pending;form.requestSubmit();}
 }
});
// The server authorizes Undo; this timer only retires its short-lived control.
function expireUndo(){document.querySelectorAll('[data-undo-until]').forEach(form=>{if(Date.now()>=Date.parse(form.dataset.undoUntil)){form.querySelector('button').disabled=true;form.hidden=true;}});}
expireUndo();setInterval(expireUndo,250);

// Expiry is enforced on the server; also return an idle or resumed page to sign-in.
const staffSessionEnds = Date.parse(document.body.dataset.staffSessionEnds);
if (Number.isFinite(staffSessionEnds)) {
 const checkStaffSession = () => {
  const remaining = staffSessionEnds - Date.now();
  if (remaining <= 0) window.location.replace(document.body.dataset.staffSigninUrl);
  else return window.setTimeout(checkStaffSession, remaining);
 };
 checkStaffSession();
 document.addEventListener('visibilitychange', () => {
  if (!document.hidden && Date.now() >= staffSessionEnds) checkStaffSession();
 });
 window.addEventListener('pageshow', () => {
  if (Date.now() >= staffSessionEnds) checkStaffSession();
 });
}

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
 if(e.target.closest('[data-print]')){document.querySelector('#print-status').textContent='Opening print dialog…';window.print();}
});
document.addEventListener('input',e=>{if(e.target.id==='kg')delete e.target.dataset.keypadValue;});
// HTMX prices only; final creation is a normal POST with the same server rules.
document.addEventListener('submit',e=>{if(e.target.id==='intake'){e.stopPropagation();}},true);
document.addEventListener('htmx:configRequest',e=>{const token=document.querySelector('[name=csrfmiddlewaretoken]');if(token)e.detail.headers['X-CSRFToken']=token.value;});

document.addEventListener('click',e=>{const create=e.target.closest('[data-create]');if(create){e.preventDefault();const f=create.form;if(f.reportValidity())HTMLFormElement.prototype.submit.call(f);}});

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
  el.querySelector('[data-connection-label]').textContent=navigator.onLine?'Online':'Offline';
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

// Progressive enhancement: dialogs keep ordinary links and server-validated forms.
let appDialog,dialogTrigger,dialogRequest=0;
function closeAppDialog(){if(appDialog?.open)appDialog.close();}
document.addEventListener('click',async e=>{
 const link=e.target.closest('a[data-dialog]');
 if(!link||e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
 const url=new URL(link.href,location.href);if(url.origin!==location.origin)return;
 e.preventDefault();const sequence=++dialogRequest;
 try{
  const response=await fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}});
  if(!response.ok||response.redirected){location.assign(response.url||url);return;}
  const doc=new DOMParser().parseFromString(await response.text(),'text/html');
  const content=doc.querySelector('main .stub-wrap,main .auth-card');
  if(!content){location.assign(url);return;}
  if(sequence!==dialogRequest)return;
  if(!appDialog){
   appDialog=document.createElement('dialog');appDialog.className='app-dialog';
   const close=document.createElement('button');close.className='x dialog-close';close.type='button';close.setAttribute('aria-label','Close dialog');close.textContent='×';close.addEventListener('click',closeAppDialog);
   appDialog.append(close);document.body.append(appDialog);
   appDialog.addEventListener('click',event=>{if(event.target===appDialog){const box=appDialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)closeAppDialog();}});
   appDialog.addEventListener('close',()=>{appDialog.querySelector('.dialog-content')?.remove();if(dialogTrigger?.isConnected)dialogTrigger.focus();});
  }
  appDialog.querySelector('.dialog-content')?.remove();
  content.classList.add('dialog-content');
  content.querySelectorAll('form:not([action])').forEach(form=>form.action=response.url);
  content.querySelectorAll('[id]').forEach(el=>el.id='dialog-'+el.id);
  content.querySelectorAll('label[for]').forEach(el=>el.htmlFor='dialog-'+el.htmlFor);
  const heading=content.querySelector('h2');
  if(heading){heading.id='app-dialog-title';appDialog.setAttribute('aria-labelledby',heading.id);}
  appDialog.append(content);dialogTrigger=link;
  if(!appDialog.open)appDialog.showModal();
  appDialog.querySelector('.dialog-close').focus();
 }catch(error){location.assign(url);}
});

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

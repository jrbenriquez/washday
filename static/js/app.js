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

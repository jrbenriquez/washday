document.addEventListener('click', e => {
 const digit=e.target.closest('[data-digit]');
 if(digit){const input=document.querySelector('#kg');let v=input.value;input.value=digit.dataset.digit==='clear'?'0':((v==='0'&&digit.dataset.digit!=='.'?'':v)+digit.dataset.digit);input.dispatchEvent(new Event('change',{bubbles:true}));}
 const step=e.target.closest('[data-step]');if(step){const input=step.parentElement.querySelector('input');input.value=Math.max(0,Math.min(9999,Number(input.value)+Number(step.dataset.step)));input.dispatchEvent(new Event('change',{bubbles:true}));}
 if(e.target.closest('[data-print]')){document.querySelector('#print-status').textContent='Opening print dialog…';window.print();}
});
// HTMX prices only; final creation is a normal POST with the same server rules.
document.addEventListener('submit',e=>{if(e.target.id==='intake'){e.stopPropagation();}},true);
document.addEventListener('htmx:configRequest',e=>{const token=document.querySelector('[name=csrfmiddlewaretoken]');if(token)e.detail.headers['X-CSRFToken']=token.value;});

document.addEventListener('click',e=>{const create=e.target.closest('[data-create]');if(create){e.preventDefault();const f=create.form;if(f.reportValidity())HTMLFormElement.prototype.submit.call(f);}});

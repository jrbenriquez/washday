const qr=document.getElementById('install-qr');
if(qr && typeof qrcode==='function'){const code=qrcode(0,'M');code.addData(qr.dataset.url);code.make();qr.innerHTML=code.createSvgTag({scalable:true,margin:3});}
setInterval(()=>document.querySelectorAll('[data-seconds]').forEach(el=>{let n=Math.max(0,Number(el.dataset.seconds)-1);el.dataset.seconds=String(n);el.textContent=n?String(n):'0 (expired)';}),1000);

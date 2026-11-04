if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true) {
 const form=document.getElementById('device-setup-form');if(form)form.hidden=false;
 const help=document.getElementById('standalone-help');if(help)help.hidden=true;
}

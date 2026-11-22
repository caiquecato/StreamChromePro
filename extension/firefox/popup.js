const button=document.getElementById('open');
const label=document.getElementById('buttonLabel');
const status=document.getElementById('status');
let busy=false, generation=0;
function fail(message){busy=false;button.disabled=false;button.setAttribute('aria-busy','false');label.textContent='Try again';status.textContent=message;status.hidden=false;}
button.addEventListener('click',()=>{
 if(busy)return;
 const requestGeneration=++generation;
 busy=true;button.disabled=true;button.setAttribute('aria-busy','true');label.textContent='Opening player';status.hidden=true;status.textContent='';
 const timeout=setTimeout(()=>fail('The player is taking too long to start. Open it from the Windows Start menu.'),25000);
 chrome.runtime.sendNativeMessage('com.caiquecato.streamchromepro',{action:'open'},response=>{
  const error=chrome.runtime.lastError;
  clearTimeout(timeout);
  if(!busy||requestGeneration!==generation)return;
  if(error){fail('Could not connect to the desktop app. Install StreamChrome PRO, then restart your browser.');return;}
  if(!response?.ok){fail('The player could not start. Open it from the Windows Start menu.');return;}
  chrome.tabs.create({url:'http://127.0.0.1:8780/'},()=>{
   if(chrome.runtime.lastError){fail('Could not open the player tab. Try again.');return;}
   window.close();
  });
 });
});

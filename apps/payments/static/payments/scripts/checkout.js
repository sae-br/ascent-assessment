(function(){
  "use strict";
  const form = document.getElementById('start-checkout');
  if (!form) return;

  form.addEventListener('submit', async function(e){
    e.preventDefault();
    const csrf = form.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    try {
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf }
      });
      if (!res.ok) throw new Error('Failed to start checkout');
      const data = await res.json();
      if (data && data.url){
        window.location = data.url;
      } else if (data.redirect){
        window.location = data.redirect;
      } else {
        alert(data.error || 'Unable to start checkout');
      }
    } catch(err){
      console.error(err);
      alert('Unable to start checkout right now. Please try again.');
    }
  });
})();
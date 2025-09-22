(function(){
  'use strict';

  // Ensure icons render after DOM is ready (lucide script is loaded in <head>)
  function initIcons(){
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initIcons);
  } else {
    initIcons();
  }

  // HTMX: attach CSRF header to all requests
  function getCookie(name){
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : null;
  }

  // htmx may not be present on every page; guard accordingly
  document.addEventListener('htmx:configRequest', function (evt) {
    const value = getCookie('csrftoken');
    if (value) evt.detail.headers['X-CSRFToken'] = value;
  });

  // Fade then remove any element marked with data-autofade (ms)
  document.addEventListener('htmx:afterSwap', function () {
    document.querySelectorAll('[data-autofade]').forEach(function (el) {
      const delay = parseInt(el.dataset.autofade || '5000', 10) || 5000; // default 5s
      window.setTimeout(function(){
        el.style.transition = 'opacity .6s';
        el.style.opacity = '0';
        window.setTimeout(function(){
          if (el && el.parentNode) el.parentNode.removeChild(el);
        }, 650);
      }, delay);
    });
  });
})();
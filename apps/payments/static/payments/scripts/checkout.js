(function(){
  "use strict";

  // --- helpers ---
  function $(sel){ return document.querySelector(sel); }
  function getCookie(name){
    const m = document.cookie.match(new RegExp('(^| )'+name+'=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : null;
  }
  function cents(n){ return parseInt(n || 0, 10) || 0; }
  function fmt(minor){ return "$" + (cents(minor) / 100).toFixed(2); }

  // --- config from DOM ---
  const cfgNode = $("#checkout-config");
  if (!cfgNode) return;

  const PUBLISHABLE_KEY = cfgNode.dataset.publishableKey;
  const CLIENT_SECRET   = cfgNode.dataset.clientSecret;
  const RETURN_URL      = cfgNode.dataset.returnUrl;
  const ASSESSMENT_ID   = cfgNode.dataset.assessmentId;

  const root = $("#price-summary");
  const btn  = "#pay-btn" ? $("#pay-btn") : null;
  const err  = $("#error-text");

  const promoInput = $('#id_promo');
  const applyBtn = $('#apply-promo');
  const promoBadge = $('#promo-badge');
  const removeBtn = $('#remove-promo');

  function initPromoUI(){
    const badgeVisible = promoBadge && getComputedStyle(promoBadge).display !== 'none';
    if (badgeVisible){
      if (promoInput){ promoInput.style.display = 'none'; }
      if (applyBtn){ applyBtn.style.display = 'none'; }
    }
  }
  initPromoUI();

  function showPromoBadge(code){
    if (promoBadge){
      const label = promoBadge.querySelector('.badge-label');
      if (label) label.textContent = code || '';
      promoBadge.style.display = 'inline-flex';
    }
    if (promoInput) {
      promoInput.disabled = true;
      promoInput.style.display = 'none';
    }
    if (applyBtn) {
      applyBtn.disabled = true;
      applyBtn.style.display = 'none';
    }
  }
  function hidePromoBadge(){
    if (promoBadge){ promoBadge.style.display = 'none'; }
    if (promoInput){ 
      promoInput.disabled = false; 
      promoInput.value = ''; 
      promoInput.style.display = '';
    }
    if (applyBtn) {
      applyBtn.disabled = false;
      applyBtn.style.display = '';
    }
  }

  function renderPriceSummaryFromDataset(){
    if (!root) return;
    const ds = root.dataset || {};
    const elSubtotal = $("#ps-subtotal");
    const elDiscount = $("#ps-discount");
    const elTax      = $("#ps-tax");
    const elTotal    = $("#ps-total");
    const showSubtotal = ds.original ? fmt(ds.original) : "$750.00";
    const showDiscount = (ds.discount && cents(ds.discount)) ? ("-" + fmt(Math.abs(cents(ds.discount)))) : "$0.00";
    const showTax      = ds.tax ? fmt(ds.tax) : "$0.00";
    const showTotal    = ds.final ? fmt(ds.final) : showSubtotal;
    if (elSubtotal) elSubtotal.textContent = showSubtotal;
    if (elDiscount) elDiscount.textContent = showDiscount;
    if (elTax)      elTax.textContent      = showTax;
    if (elTotal)    elTotal.textContent    = showTotal;
  }

  // --- Stripe setup ---
  const stripe = Stripe(PUBLISHABLE_KEY);
  function extractPiId(cs){
    if (!cs) return "";
    const m = cs.match(/^(pi_[^_]+)_secret_/);
    return m ? m[1] : "";
  }
  const __PI_ID__ = extractPiId(CLIENT_SECRET);
  if (root) root.dataset.piId = __PI_ID__;

  const elements = stripe.elements({ clientSecret: CLIENT_SECRET });

  const addressEl = elements.create('address', {
    mode: 'billing',
    fields: { phone: 'never' }
  });
  addressEl.mount('#billing-address');

  let lastAddress = {};
  let isRepricing = false;

  const paymentElement = elements.create('payment', {
    fields: {
      billingDetails: { address: 'never', email: 'never', phone: 'never', name: 'auto' }
    }
  });
  paymentElement.mount('#payment-form');

  // If server said zero due on initial render, hide payment element and set button
  (function initZeroDue(){
    if (!root) return;
    if (root.dataset.zeroDue === '1'){
      const payInit = $('#payment-form');
      if (payInit) payInit.style.display = 'none';
      const noteInit = $('#no-payment-note');
      if (noteInit) noteInit.style.display = '';
      if (btn) btn.textContent = 'Get report';
    }
  })();

  function setProcessing(on){
    if (!btn) return;
    btn.disabled = !!on;
    btn.textContent = on ? 'Processing…' : (root && root.dataset.zeroDue === '1' ? 'Get report' : 'Pay now');
  }

  async function repriceNow(promoCode){
    if (isRepricing) return; // debounce overlapping calls
    isRepricing = true;
    if (err) err.textContent = '';
    const csrf = getCookie('csrftoken');
    const piId = (root && root.dataset && root.dataset.piId) ? root.dataset.piId : __PI_ID__;
    try{
      const res = await fetch('/payments/reprice/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf || '' },
        body: JSON.stringify({
          assessment_id: ASSESSMENT_ID,
          promo_code: promoCode || ($('#id_promo') ? $('#id_promo').value : ''),
          billing_address: lastAddress || {},
          pi_id: piId,
        })
      });
      if (!res.ok) throw new Error('Reprice failed');
      const data = await res.json();

      // Promo badge/UI: if discount applied (>0), lock the input and show badge
      const discountApplied = (data && data.discount_minor && cents(data.discount_minor) > 0);
      if (discountApplied){
        const codeVal = (promoInput && promoInput.value) ? promoInput.value.trim().toUpperCase() : '';
        showPromoBadge(codeVal);
      } else {
        // invalid or removed
        hidePromoBadge();
      }

      // update datasets
      if (root && root.dataset){
        root.dataset.original = String(data.original_amount_minor);
        root.dataset.discount = String(data.discount_minor || 0);
        root.dataset.tax      = String(data.tax_minor || 0);
        root.dataset.final    = String(data.final_amount_minor);
        root.dataset.zeroDue  = data.zero_due ? '1' : '0';
      }

      // refresh UI
      renderPriceSummaryFromDataset();
      if (btn) btn.textContent = (data.zero_due ? 'Get report' : 'Pay now');

      // hide/show payment element and note
      const pay = $('#payment-form');
      const note = $('#no-payment-note');
      if (pay)  pay.style.display  = data.zero_due ? 'none' : '';
      if (note) note.style.display = data.zero_due ? '' : 'none';
    } catch(e){
      console.error(e);
      if (err) err.textContent = 'Could not update price. Please try again.';
    } finally {
      isRepricing = false;
    }
  }

  // When address completes, reprice
  addressEl.on('change', function(evt){
    if (evt && evt.value && evt.value.address){
      lastAddress = evt.value.address;
    }
    if (evt && evt.complete){
      repriceNow();
    }
  });

  // Apply promo click
  if (applyBtn){
    applyBtn.addEventListener('click', function(){ repriceNow(); });
  }

  if (removeBtn){
    removeBtn.addEventListener('click', function(){
      hidePromoBadge();
      if (err) err.textContent = '';
      // Trigger reprice with no code
      repriceNow('');
    });
  }

  async function completeZeroFlow(){
    const csrf = getCookie('csrftoken');
    try{
      const res = await fetch('/payments/complete-zero/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf || '' },
        body: JSON.stringify({
          assessment_id: ASSESSMENT_ID,
          promo_code: $('#id_promo') ? $('#id_promo').value : '',
          billing_address: lastAddress || {},
        })
      });
      if (!res.ok) throw new Error('Zero-complete failed');
      const data = await res.json();
      if (data && data.ok && data.redirect){
        window.location.href = data.redirect;
        return;
      }
      throw new Error('Unexpected zero-complete response');
    } catch(e){
      console.error(e);
      if (err) err.textContent = 'Could not finalize free checkout. Please try again.';
    }
  }

  if (btn){
    btn.addEventListener('click', async function(){
      if (!root) return;
      err && (err.textContent = '');
      setProcessing(true);

      if (root.dataset.zeroDue === '1'){
        await completeZeroFlow();
        setProcessing(false);
        return;
      }

      try{
        const result = await stripe.confirmPayment({
          elements,
          confirmParams: { return_url: RETURN_URL },
          redirect: 'if_required',
        });

        if (result.error){
          err && (err.textContent = result.error.message || 'Payment failed. Try another card.');
          return;
        }
        const pi = result.paymentIntent;
        if (pi && pi.status === 'succeeded'){
          const ret = RETURN_URL;
          window.location.href = ret + (ret.includes('?') ? '&' : '?') + 'pi=' + pi.id;
          return;
        }
        err && (err.textContent = 'Verifying your payment… If nothing happens, please refresh.');
      } catch(e){
        console.error(e);
        if (err) err.textContent = 'Unexpected error. Please try again.';
      } finally {
        setProcessing(false);
      }
    });
  }

  // initial render from server-provided dataset
  renderPriceSummaryFromDataset();
})();
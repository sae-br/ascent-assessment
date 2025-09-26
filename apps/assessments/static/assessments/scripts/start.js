// apps/assessments/static/assessments/scripts/start.js
(function () {
  const steps = Array.from(document.querySelectorAll('.step'));
  const totalSteps = steps.length; // intro + N questions + final
  const stepTotalEl = document.getElementById('stepTotal');
  const stepNumEl = document.getElementById('stepNum');
  const progressFill = document.querySelector('.progress-fill');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const formError = document.getElementById('formError');

  stepTotalEl.textContent = totalSteps;

  let idx = 0; // active step index

  function show(i) {
    clearError();
    steps.forEach((s, n) => s.classList.toggle('is-active', n === i));

    // Back button behavior
    const onIntro = i === 0;
    prevBtn.style.visibility = onIntro ? 'hidden' : 'visible';
    prevBtn.disabled = onIntro;
    prevBtn.setAttribute('aria-hidden', onIntro ? 'true' : 'false');

    // Next button on last step
    const onLast = i === totalSteps - 1;
    nextBtn.style.display = onLast ? 'none' : '';
    nextBtn.disabled = false;

    // Progress + step number
    stepNumEl.textContent = i + 1;
    const pct = Math.round((i / (totalSteps - 1)) * 100);
    progressFill.style.width = pct + '%';
  }

  function currentQuestionAnswered() {
    const active = steps[idx];
    const radios = active.querySelectorAll('input[type="radio"][name^="question_"]');
    if (!radios.length) return true; // intro and final step have no radios
    return Array.from(radios).some(r => r.checked);
  }

  function showError(msg) {
    if (!formError) return;
    formError.textContent = msg || 'Please select an option to continue.';
    formError.hidden = false;
  }
  function clearError() {
    if (!formError) return;
    formError.hidden = true;
  }

  nextBtn.addEventListener('click', function () {
    if (!currentQuestionAnswered()) {
      showError('Please select an option to continue.');
      const first = steps[idx].querySelector('input[type="radio"]');
      if (first) first.focus();
      return;
    }
    clearError();
    if (idx < totalSteps - 1) {
      idx += 1;
      show(idx);
    }
  });

  prevBtn.addEventListener('click', function () {
    if (idx > 0) {
      idx -= 1;
      show(idx);
    }
  });

  // Make the whole label clickable and reflect selected state
  document.querySelectorAll('.choice').forEach(lbl => {
    lbl.addEventListener('click', () => {
      const input = lbl.querySelector('input[type="radio"]');
      if (!input) return;
      input.checked = true;

      // Clear selected state for this radio group
      const groupName = input.name;
      document.querySelectorAll(`input[name="${groupName}"]`).forEach(r => {
        const l = r.closest('.choice');
        if (l) l.classList.remove('is-selected');
      });

      // Set selected state for the clicked label
      lbl.classList.add('is-selected');
      clearError();
    });
  });

  // Keep selected styling in sync when using keyboard
  document.querySelectorAll('input[type="radio"]').forEach(r => {
    r.addEventListener('change', () => {
      const groupName = r.name;
      document.querySelectorAll(`input[name="${groupName}"]`).forEach(rr => {
        const l = rr.closest('.choice');
        if (l) l.classList.toggle('is-selected', rr.checked);
      });
      clearError();
    });
  });

  show(0);
})();
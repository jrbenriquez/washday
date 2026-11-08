// Django formsets retain their indices so removed rows remain valid on submission.
document.querySelectorAll('[data-onboarding-group]').forEach(group => {
  const prefix = group.dataset.onboardingGroup;
  const total = group.querySelector(`[name="${prefix}-TOTAL_FORMS"]`);
  const rows = group.querySelector('[data-rows]');
  function updateRow(row) {
    const checkbox = row.querySelector('[name$="-DELETE"]');
    if (checkbox.checked) {
      row.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]), select').forEach(field => {
        field.required = false;
      });
    } else {
      row.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]), select').forEach(field => {
        field.required = true;
      });
    }
  }
  rows.querySelectorAll('[data-onboarding-row]').forEach(updateRow);
  rows.addEventListener('change', event => {
    if (event.target.name.endsWith('-DELETE')) updateRow(event.target.closest('[data-onboarding-row]'));
  });
  group.querySelector('[data-add-row]').addEventListener('click', () => {
    if (Number(total.value) >= 100) return;
    const fragment = group.querySelector('template').content.cloneNode(true);
    fragment.querySelectorAll('*').forEach(node => {
      for (const attr of [...node.attributes]) {
        if (attr.value.includes('__prefix__')) node.setAttribute(attr.name, attr.value.replaceAll('__prefix__', total.value));
      }
    });
    rows.append(fragment);
    total.value = Number(total.value) + 1;
    const row = rows.lastElementChild;
    updateRow(row);
    row.querySelector('input:not([type="hidden"])').focus();
  });
});

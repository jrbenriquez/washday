// Retain formset indices and hidden DELETE values so the server validates removals.
const onboardingForm = document.querySelector('#shop-onboarding');
const status = onboardingForm?.querySelector('[data-onboarding-status]');
onboardingForm?.classList.add('onboarding-enhanced');

document.querySelectorAll('[data-onboarding-group]').forEach(group => {
  const prefix = group.dataset.onboardingGroup;
  const total = group.querySelector(`[name="${prefix}-TOTAL_FORMS"]`);
  const rows = group.querySelector('[data-rows]');
  const addButton = group.querySelector('[data-add-row]');

  function updateRow(row) {
    const checkbox = row.querySelector('[name$="-DELETE"]');
    const name = row.querySelector('[name$="-name"]').value.trim() || 'item';
    const button = row.querySelector('[data-remove-row]');
    const removed = checkbox.checked;
    row.classList.toggle('is-removed', removed);
    row.querySelector('[data-removed-summary]').hidden = !removed;
    row.querySelector('[data-removed-summary]').textContent = `${name} removed`;
    row.querySelector('[data-undo-label]').hidden = !removed;
    button.hidden = false;
    button.setAttribute('aria-label', `${removed ? 'Undo removal of' : 'Remove'} ${name}`);
    row.querySelectorAll('[data-row-fields] input, [data-row-fields] select').forEach(field => {
      field.required = !removed;
    });
  }

  rows.querySelectorAll('[data-onboarding-row]').forEach(updateRow);
  rows.addEventListener('input', event => {
    if (event.target.name.endsWith('-name')) updateRow(event.target.closest('[data-onboarding-row]'));
  });
  rows.addEventListener('change', event => {
    if (event.target.name.endsWith('-DELETE')) updateRow(event.target.closest('[data-onboarding-row]'));
  });
  rows.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-row]');
    if (!button) return;
    const row = button.closest('[data-onboarding-row]');
    const checkbox = row.querySelector('[name$="-DELETE"]');
    checkbox.checked = !checkbox.checked;
    updateRow(row);
    status.textContent = checkbox.checked ? `${row.querySelector('[data-removed-summary]').textContent}. Choose Undo to restore it.` : 'Item restored.';
    button.focus();
  });
  addButton.addEventListener('click', () => {
    if (Number(total.value) >= 100) return;
    const fragment = group.querySelector('template').content.cloneNode(true);
    fragment.querySelectorAll('*').forEach(node => {
      for (const attr of [...node.attributes]) {
        if (attr.value.includes('__prefix__')) node.setAttribute(attr.name, attr.value.replaceAll('__prefix__', total.value));
      }
    });
    rows.append(fragment);
    total.value = Number(total.value) + 1;
    addButton.disabled = Number(total.value) >= 100;
    const row = rows.lastElementChild;
    updateRow(row);
    row.querySelector('[name$="-name"]').focus();
    status.textContent = prefix === 'services' ? 'New service added. Enter a name, billing unit and price.' : 'New piece item added. Enter a name, unit and price.';
  });
});

onboardingForm?.querySelector('[data-error-summary]')?.focus();

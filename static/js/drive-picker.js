(() => {
  const form = document.getElementById('drive-picker-form');
  if (!form) return;
  const button = document.getElementById('drive-pick');
  const status = document.getElementById('drive-picker-status');
  button.addEventListener('click', async () => {
    button.disabled = true;
    status.textContent = 'Opening Google Drive…';
    try {
      if (!window.gapi) throw new Error('Google Picker could not load. Refresh and try again.');
      await new Promise((resolve, reject) => gapi.load('picker', { callback: resolve, onerror: reject, timeout: 15000, ontimeout: reject }));
      const response = await fetch(form.dataset.tokenUrl, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value }
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Reconnect Google Drive and try again.');
      const view = new google.picker.DocsView(google.picker.ViewId.FOLDERS)
        .setIncludeFolders(true).setSelectFolderEnabled(true).setMimeTypes('application/vnd.google-apps.folder');
      new google.picker.PickerBuilder().addView(view)
        .setOAuthToken(data.access_token).setDeveloperKey(form.dataset.apiKey)
        .setAppId(form.dataset.appId).setOrigin(window.location.origin)
        .setCallback(result => {
          if (result.action === google.picker.Action.PICKED) {
            document.getElementById('drive-folder-id').value = result.docs[0].id;
            form.submit();
          }
        }).build().setVisible(true);
      status.textContent = '';
    } catch (error) {
      status.textContent = error?.message || 'Unable to open Google Picker. Try again.';
    } finally {
      button.disabled = false;
    }
  });
})();

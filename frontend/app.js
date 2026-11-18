/* Assignment 3 frontend using the API Gateway-generated JavaScript SDK.
 * The SDK was generated from the user's deployed /prod API stage.
 * Keep config.js from the working S3 website; it supplies only the class-project API key.
 */
const cfg = window.PHOTO_APP_CONFIG || {};
const statusEl = document.getElementById('status');
const gallery = document.getElementById('gallery');
const countEl = document.getElementById('result-count');
let apiClient = null;

function status(text, error = false) {
  statusEl.textContent = text;
  statusEl.style.color = error ? '#ff9c98' : '#54dec2';
}

function ready() {
  if (!cfg.apiKey || cfg.apiKey.startsWith('REPLACE')) {
    status('Keep your working frontend/config.js with the actual API Gateway API key value.', true);
    return false;
  }
  if (typeof apigClientFactory === 'undefined') {
    status('The generated API Gateway SDK was not loaded. Upload the entire sdk/ folder.', true);
    return false;
  }
  if (!apiClient) {
    // The generated apigClient.js already contains the deployed /prod base URL.
    // API keys are visible in any public browser app; they are not authentication.
    apiClient = apigClientFactory.newClient({ apiKey: cfg.apiKey });
  }
  return true;
}

function apiError(err) {
  if (err && err.response) {
    const data = err.response.data;
    const message = typeof data === 'string' ? data : JSON.stringify(data);
    return 'API ' + err.response.status + ': ' + String(message).slice(0, 300);
  }
  return err && err.message ? err.message : String(err);
}

function render(items) {
  gallery.replaceChildren();
  countEl.textContent = items.length + ' photo' + (items.length === 1 ? '' : 's');
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No matching photos. Try another label.';
    gallery.append(empty);
    return;
  }
  for (const item of items) {
    const card = document.createElement('article');
    card.className = 'result';
    const img = document.createElement('img');
    img.src = item.url;
    img.alt = 'Matched photo';
    img.loading = 'lazy';
    const chips = document.createElement('div');
    chips.className = 'chips';
    for (const label of (item.labels || []).slice(0, 12)) {
      const chip = document.createElement('span');
      chip.textContent = label;
      chips.append(chip);
    }
    card.append(img, chips);
    gallery.append(card);
  }
}

document.getElementById('search-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!ready()) return;
  const query = document.getElementById('query').value.trim();
  if (!query) return;
  status('Searching…');
  try {
    const response = await apiClient.searchGet({ q: query }, {}, {});
    const data = typeof response.data === 'string' ? JSON.parse(response.data) : response.data;
    render(data.results || []);
    status('Search complete.');
  } catch (err) {
    status(apiError(err), true);
  }
});

document.getElementById('upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!ready()) return;
  const form = document.getElementById('upload-form');
  const file = document.getElementById('photo').files[0];
  if (!file) return;
  if (!['image/jpeg', 'image/png'].includes(file.type)) {
    status('Choose a JPG or PNG image.', true);
    return;
  }
  const labels = document.getElementById('custom-labels').value
    .split(',').map(s => s.trim()).filter(Boolean).join(', ');
  const key = Date.now() + '-' + file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
  status('Uploading…');
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    await apiClient.photosPut({
      key: key,
      'Content-Type': file.type,
      'x-amz-meta-customLabels': labels
    }, bytes, {});
    status('Upload complete. Rekognition indexing is asynchronous; search in a few moments.');
    form.reset();
  } catch (err) {
    status(apiError(err), true);
  }
});

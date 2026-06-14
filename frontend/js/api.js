// Thin fetch wrapper around the backend API.
const API = {
  async _json(url, opts) {
    const r = await fetch(url, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `请求失败 (${r.status})`);
    return data;
  },
  state() { return this._json('/api/state'); },
  history() { return this._json('/api/history'); },
  series(key) { return this._json('/api/series/' + key); },
  lore(key) { return this._json('/api/lore/' + key); },
  tech() { return this._json('/api/tech'); },
  setResearch(tech_id) {
    return this._json('/api/tech/research', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tech_id }),
    });
  },
  peace(body) {
    return this._json('/api/peace', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  },
  war(body) {
    return this._json('/api/war', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  },
  runTurn(policy_text, chosen_options) {
    return this._json('/api/turn', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ policy_text, chosen_options }),
    });
  },
  reset() { return this._json('/api/reset', { method: 'POST' }); },
  rewind(turn) { return this._json('/api/rewind/' + turn, { method: 'POST' }); },
  listSaves() { return this._json('/api/saves'); },
  createSave(name) {
    return this._json('/api/saves', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
  },
  loadSave(id) { return this._json('/api/saves/' + id + '/load', { method: 'POST' }); },
  deleteSave(id) { return this._json('/api/saves/' + id, { method: 'DELETE' }); },
  getConfig() { return this._json('/api/config'); },
  setConfig(cfg) {
    return this._json('/api/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    });
  },
};

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
  /**
   * Streaming turn: POST /api/turn/stream via SSE.
   * Calls onHeartbeat() periodically while waiting, resolves with the result on completion.
   */
  async runTurnStream(policy_text, chosen_options, onHeartbeat) {
    const r = await fetch('/api/turn/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ policy_text, chosen_options }),
    });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      throw new Error(data.detail || `请求失败 (${r.status})`);
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // Parse SSE events from buffer
      const lines = buf.split('\n');
      buf = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'result') return evt.data;
            if (evt.type === 'error') throw new Error(evt.message);
          } catch (e) {
            if (e.message && !e.message.includes('JSON')) throw e;
          }
        } else if (line.startsWith(': ') || line.startsWith(':')) {
          // SSE comment (heartbeat) — call callback
          if (onHeartbeat) onHeartbeat();
        }
      }
    }
    throw new Error('推演连接意外断开');
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

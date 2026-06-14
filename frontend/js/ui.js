// Main UI controller.
const UI = {
  state: null,
  prev: {},          // faction_key -> previous stat snapshot (for deltas)
  selected: 'song',
  config: null,
  lang: 'plain',     // 'classic' 文言 | 'plain' 白话
  lastRes: null,     // last turn result (for re-rendering the drawer on lang switch)

  ERAS: [
    [1068, 1077, '熙宁'], [1078, 1085, '元丰'], [1086, 1093, '元祐'],
    [1094, 1097, '绍圣'], [1098, 1100, '元符'], [1101, 1101, '建中靖国'],
    [1102, 1106, '崇宁'], [1107, 1110, '大观'], [1111, 1118, '政和'],
  ],
  MONTHS: ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊'],

  STATS_MAIN: [
    { k: 'economy', label: '经济', max: 250, unit: '' },
    { k: 'tech', label: '科技', max: 100, unit: '' },
    { k: 'military', label: '军力', max: 130, unit: '' },
    { k: 'stability', label: '政治稳定', max: 100, unit: '' },
    { k: 'welfare', label: '民生', max: 100, unit: '' },
    { k: 'army', label: '兵力', max: 260, unit: '万' },
  ],

  reign(year) {
    let era = this.ERAS.find(e => year >= e[0] && year <= e[1]);
    if (era) {
      const n = year - era[0] + 1;
      return `${era[2]}${n === 1 ? '元' : n}年`;
    }
    return `公元${year}年`;
  },

  async init() {
    document.getElementById('btnVideo').onclick = () => this.exportVideo();
    document.getElementById('btnSaves').onclick = () => this.openSaves();
    document.getElementById('savesClose').onclick = () => document.getElementById('savesModal').hidden = true;
    document.getElementById('btnDoSave').onclick = () => this.doSave();
    document.getElementById('btnConfig').onclick = () => this.openConfig();
    document.getElementById('btnReset').onclick = () => this.reset();
    document.getElementById('btnRunTurn').onclick = () => this.runTurn();
    document.getElementById('narrClose').onclick = () => document.getElementById('narrativeDrawer').hidden = true;
    document.getElementById('narrLang').onclick = () => this.toggleLang();
    document.querySelectorAll('.tab').forEach(t =>
      t.onclick = () => this.switchTab(t.dataset.tab));
    this.bindConfigModal();
    document.getElementById('peaceCancel').onclick = () => document.getElementById('peaceModal').hidden = true;
    document.getElementById('peaceConfirm').onclick = () => this.doPeace();
    document.getElementById('warClose').onclick = () => document.getElementById('warModal').hidden = true;
    document.getElementById('warConfirm').onclick = () => this.doWar();

    await GameMap.init(key => this.selectFaction(key, true));
    this.config = await API.getConfig();
    this.renderProvider();
    await this.refresh();
  },

  async refresh() {
    this.state = await API.state();
    GameMap.setStates(this.state.factions);
    this.renderTop();
    this.renderLegend();
    this.renderState();
    this.renderPowers();
    this.renderPolicyOptions();
    this.renderActivePolicies();
    await this.renderChronicle();
  },

  fac(key) { return this.state.factions.find(f => f.faction_key === key); },

  renderProvider() {
    const names = { mock: '离线推演', anthropic: 'Anthropic', openai: 'OpenAI兼容' };
    const p = this.config.provider;
    const isMock = p === 'mock';

    const badge = document.getElementById('providerBadge');
    badge.textContent = '引擎: ' + (names[p] || p);
    badge.classList.toggle('mock', isMock);
    badge.classList.toggle('live', !isMock);

    const notice = document.getElementById('engineNotice');
    if (isMock) {
      notice.className = 'engine-notice mock';
      notice.innerHTML = '⚠ 当前为<b>离线推演</b>（mock）：结果由本地规则即时生成，<b>不经过大模型</b>。如需真实 AI 推演请点「⚙ 设置」切换。';
    } else {
      notice.className = 'engine-notice live';
      notice.innerHTML = `✓ <b>真实大模型推演</b>：${names[p] || p} · ${this.esc(this.config.model || '')}。每回合约需数十秒，请耐心等待。`;
    }
    const btn = document.getElementById('btnRunTurn');
    if (!btn.classList.contains('loading'))
      btn.textContent = isMock ? '⊳ 推演本年（离线·即时）' : '⊳ 推演本年（前进一年）';
  },

  renderTop() {
    const y = this.state.year;
    document.getElementById('reign').innerHTML =
      `${this.reign(y)} <span class="ad">公元${y}年</span>`;
    const s = this.fac('song');
    const items = [
      ['国库', Math.round(s.treasury), '万贯'],
      ['人口', Math.round(s.population), '万'],
      ['经济', Math.round(s.economy), ''],
      ['军力', Math.round(s.military), ''],
      ['科技', Math.round(s.tech), ''],
      ['稳定', Math.round(s.stability), ''],
      ['民生', Math.round(s.welfare), ''],
      ['回合', this.state.turn, ''],
    ];
    document.getElementById('topstats').innerHTML = items.map(
      ([l, v, u]) => `<div class="topstat"><span class="lbl">${l}</span>
        <span class="val">${v}<small style="font-size:11px"> ${u}</small></span></div>`).join('');
  },

  renderLegend() {
    const rows = this.state.factions.map(f =>
      `<div class="lg-row" data-key="${f.faction_key}">
        <span class="sw" style="background:${f.color}"></span>${f.name}</div>`).join('');
    const el = document.getElementById('maplegend');
    el.innerHTML = `<div class="lg-title">天下列国</div>${rows}`;
    el.querySelectorAll('.lg-row').forEach(r =>
      r.onclick = () => this.selectFaction(r.dataset.key, true));
  },

  selectFaction(key, fly) {
    this.selected = key;
    if (fly) GameMap.flyTo(key);
    this.switchTab('state');
    this.renderState();
  },

  async renderState() {
    const f = this.fac(this.selected) || this.fac('song');
    const prev = this.prev[f.faction_key];
    const delta = (k) => {
      if (!prev) return '';
      const d = +(f[k] - prev[k]).toFixed(1);
      if (Math.abs(d) < 0.05) return '';
      return `<span class="delta ${d > 0 ? 'up' : 'down'}">${d > 0 ? '▲' : '▼'}${Math.abs(d)}</span>`;
    };
    const cards = this.STATS_MAIN.map(st => {
      const v = f[st.k]; const pct = Math.min(100, (v / st.max) * 100);
      return `<div class="statcard">
        <div class="k">${st.label}</div>
        <div class="v">${Math.round(v)}<small>${st.unit}</small>${delta(st.k)}</div>
        <div class="bar"><span style="width:${pct}%"></span></div>
      </div>`;
    }).join('');

    const isPlayer = f.is_player;
    const relLine = isPlayer ? '' :
      `<div class="statcard" style="grid-column:1/-1">
        <div class="k">对大宋外交</div>
        <div class="v" style="color:${f.relation >= 0 ? 'var(--good)' : 'var(--bad)'}">
          ${Math.round(f.relation)} <small>${this.relWord(f.relation)}</small>${delta('relation')}</div>
        <div class="bar"><span style="width:${(f.relation + 100) / 2}%"></span></div>
      </div>`;

    document.getElementById('pane-state').innerHTML = `
      <div class="dash-head">
        <h3><span class="dot" style="background:${f.color}"></span>${f.name}
          ${isPlayer ? '<span style="color:var(--vermilion);font-size:13px">（朕躬）</span>' : ''}</h3>
        <span class="info">国库 ${Math.round(f.treasury)} 万贯</span>
      </div>
      <div class="faction-tag">${this.esc(f.info || '')}</div>
      <div class="now-box">
        <div class="now-label">📜 此刻近况 · 公元${this.state.year}年</div>
        <div class="now-text">${this.esc(f.note || '承平无事，暂无新动向。')}</div>
      </div>
      ${this.budgetBox(f)}
      <div class="statgrid">${cards}${relLine}</div>
      <div class="section-title">国势变迁（经济 / 军力 / 科技）</div>
      <canvas class="spark" id="spark" width="376" height="60"></canvas>
      <div class="section-title">文明志 · 史地文化</div>
      <div class="lore-box" id="loreBox">加载中…</div>`;

    this.drawSpark(f.faction_key);
    this.renderLore(f.faction_key);
  },

  async renderLore(key) {
    const box = document.getElementById('loreBox');
    if (!box) return;
    try {
      if (!this._lore) this._lore = {};
      if (this._lore[key] === undefined) this._lore[key] = (await API.lore(key)).detail;
      // selection may have changed while awaiting; only paint if still current
      if (this.selected !== key && !(this.selected === 'song' && key === 'song')) return;
      box.innerHTML = (this._lore[key] || '').split('\n').map(line => {
        const m = line.match(/^【(.+?)】([\s\S]*)$/);
        return m ? `<p class="lore-line"><b>【${m[1]}】</b>${this.esc(m[2])}</p>`
                 : `<p class="lore-line">${this.esc(line)}</p>`;
      }).join('');
    } catch { box.textContent = '（详解加载失败）'; }
  },

  budgetBox(f) {
    const b = f.budget || {};
    if (b.income == null) return '';
    const net = b.net;
    const warn = f.bankrupt ? `<div class="bk-warn">⚠ 国库告罄 · ${f.occupied ? '已被占领' : '濒临破产'}：军队欠饷哗变、民生凋敝、政局动荡</div>` : '';
    return `<div class="budget-box">
      <div class="bb-row"><span>年度收支（万贯）</span>
        <b class="${net >= 0 ? 'pos' : 'neg'}">${net >= 0 ? '盈余 +' : '亏空 '}${net}</b></div>
      <div class="bb-line">
        <span class="bb-i">税收 +${b.income}</span>
        <span class="bb-e">军费 −${b.upkeep}</span>
        <span class="bb-e">行政 −${b.admin}</span>
        ${b.court > 0 ? `<span class="bb-e" title="国库充盈则宫廷营造、赏赐、奢靡渐增">宫廷 −${b.court}</span>` : ''}
      </div>${warn}</div>`;
  },

  relWord(r) {
    if (r >= 70) return '亲善'; if (r >= 30) return '友好';
    if (r >= -10) return '中立'; if (r >= -50) return '紧张'; return '敌对';
  },

  async drawSpark(key) {
    let series = [];
    try { series = await API.series(key); } catch { return; }
    const cv = document.getElementById('spark');
    if (!cv) return;
    const ctx = cv.getContext('2d');
    ctx.clearRect(0, 0, cv.width, cv.height);
    if (series.length < 2) {
      ctx.fillStyle = '#9b8e6e'; ctx.font = '12px serif';
      ctx.fillText('（推演数回合后显示走势）', 12, 34); return;
    }
    const metrics = [['economy', '#b3261e'], ['military', '#2e7d6b'], ['tech', '#c9a24b']];
    const W = cv.width, H = cv.height, pad = 6;
    metrics.forEach(([m, color]) => {
      const vals = series.map(s => s[m]);
      const lo = Math.min(...vals), hi = Math.max(...vals);
      const rng = hi - lo || 1;
      ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 1.8;
      series.forEach((s, i) => {
        const x = pad + (i / (series.length - 1)) * (W - 2 * pad);
        const y = H - pad - ((s[m] - lo) / rng) * (H - 2 * pad);
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.stroke();
    });
  },

  renderPowers() {
    const head = `<tr><th class="name">势力</th><th>国库</th><th>经济</th><th>军力</th>
      <th>科技</th><th>对宋</th><th></th></tr>`;
    const rows = this.state.factions.map(f => {
      const tcolor = f.treasury <= 0 ? 'var(--bad)' : 'inherit';
      const flag = (f.occupied ? '<span class="tag-occ">沦陷</span>' : '')
                 + (f.at_war ? '<span class="tag-war">交战</span>' : '')
                 + (f.bankrupt ? '<span class="tag-bank">破产</span>' : '');
      // 同一位置：和平→开战；交战中→议和
      const act = (!f.is_player)
        ? (f.at_war
           ? `<button class="btn ghost sm peace-btn" data-key="${f.faction_key}">议和</button>`
           : `<button class="btn ghost sm war-btn" data-key="${f.faction_key}">开战</button>`)
        : '';
      return `<tr class="${f.is_player ? 'me' : ''}" data-key="${f.faction_key}">
        <td class="name"><span class="dot" style="background:${f.color}"></span>${f.name}${flag}</td>
        <td style="color:${tcolor}">${Math.round(f.treasury)}</td>
        <td>${Math.round(f.economy)}</td><td>${Math.round(f.military)}</td>
        <td>${Math.round(f.tech)}</td>
        <td class="rel" style="color:${f.is_player ? '#888' : (f.relation >= 0 ? 'var(--good)' : 'var(--bad)')}">
          ${f.is_player ? '—' : Math.round(f.relation)}</td>
        <td>${act}</td>
      </tr>`;
    }).join('');
    const el = document.getElementById('pane-powers');
    el.innerHTML = `<table class="powers">${head}${rows}</table>`;
    el.querySelectorAll('tr[data-key]').forEach(tr =>
      tr.onclick = (e) => { if (!e.target.classList.contains('peace-btn')) this.selectFaction(tr.dataset.key, true); });
    el.querySelectorAll('.peace-btn').forEach(b =>
      b.onclick = (e) => { e.stopPropagation(); this.openPeace(b.dataset.key); });
    el.querySelectorAll('.war-btn').forEach(b =>
      b.onclick = (e) => { e.stopPropagation(); this.openWar(b.dataset.key); });
  },

  renderPolicyOptions() {
    const opts = (this.state.last_turn && this.state.last_turn.options) || this.defaultOptions();
    const list = document.getElementById('optionList');
    list.innerHTML = opts.map((o, i) => `
      <label class="option" data-i="${i}">
        <input type="checkbox" value="${(o.title || '').replace(/"/g, '&quot;')}" />
        <div><div class="ot">${o.title || ''}</div><div class="od">${o.desc || ''}</div></div>
      </label>`).join('');
    list.querySelectorAll('.option').forEach(op => {
      const cb = op.querySelector('input');
      op.onclick = (e) => { if (e.target !== cb) cb.checked = !cb.checked; op.classList.toggle('checked', cb.checked); };
    });
  },

  renderActivePolicies() {
    const el = document.getElementById('activePolicies');
    const ap = this.state.active_policies || [];
    if (!ap.length) {
      el.innerHTML = '<div class="ap-empty">尚无长期国策。所颁政策若立为国策，将在此持续生效，并被纳入此后每回合的推演（计其累积影响）。</div>';
      return;
    }
    const chipize = (obj, cls) => Object.entries(obj || {}).filter(([, v]) => Math.abs(v) >= 0.05)
      .map(([k, v]) => `<span class="eff ${cls || (v > 0 ? 'pos' : 'neg')}">${this.statName(k)}${v > 0 ? '+' : ''}${v}</span>`).join('');
    el.innerHTML = ap.map(p => {
      const chips = chipize(p.current_effect);
      const steady = chipize(p.steady_effect, 'steady');
      const hl = p.half_life;
      const mature = hl == null ? '' : (hl >= 15 ? `大后期·半衰期${hl}年` : `半衰期${hl}年`);
      return `<div class="ap-item">
        <div class="ap-title">📜 ${this.esc(p.title)}
          <span class="ap-since">${p.months ? '已行 ' + p.months + ' 年' : '本年新立'}</span></div>
        ${p.summary ? `<div class="ap-sum">${this.esc(p.summary)}</div>` : ''}
        ${chips ? `<div class="ap-eff"><span class="ap-eff-l">本年效力</span>${chips}</div>` : ''}
        ${steady ? `<div class="ap-eff"><span class="ap-eff-l">长期渐增至</span>${steady}</div>` : ''}
        ${p.enacted_label ? `<div class="ap-meta">颁于 ${this.esc(p.enacted_label)}${mature ? ' · ' + mature : ''}</div>` : ''}
      </div>`;
    }).join('');
  },

  defaultOptions() {
    return [
      { title: '整饬吏治，裁汰冗官', desc: '核实员额、澄清选格，省靡费而肃纲纪。' },
      { title: '兴修水利，劝课农桑', desc: '征夫治河、垦辟荒田，以实仓廪、安黎庶。' },
      { title: '增市舶以广海贸', desc: '招徕番商、广通有无，充盈府库。' },
    ];
  },

  async runTurn() {
    const btn = document.getElementById('btnRunTurn');
    const status = document.getElementById('turnStatus');
    const policy = document.getElementById('policyText').value;
    const chosen = [...document.querySelectorAll('#optionList input:checked')].map(c => c.value);
    if (!policy.trim() && chosen.length === 0 &&
        !confirm('本年未颁新政，是否萧规曹随、直接推进一年？')) return;

    // snapshot current stats for delta display
    this.prev = {}; this.state.factions.forEach(f => this.prev[f.faction_key] = { ...f });

    btn.disabled = true; btn.classList.add('loading');
    status.className = 'turn-status'; status.textContent = '';
    try {
      const res = await API.runTurn(policy, chosen);
      document.getElementById('policyText').value = '';
      if (res.map_changed) await GameMap.loadFactions();   // LLM 裁决的领土变更，重绘地图
      await this.refresh();
      this.showNarrative(res);
      if (res.territory_changes && res.territory_changes.length) {
        const names = res.territory_changes.map(t => t.name || '').filter(Boolean).join('、');
        if (names) document.getElementById('turnStatus').textContent = '疆域有变：' + names + '（地图已更新）';
      }
    } catch (e) {
      status.className = 'turn-status err';
      status.textContent = '推演失败：' + e.message + '（可在「设置」切换为离线推演试玩）';
    } finally {
      btn.disabled = false; btn.classList.remove('loading');
    }
  },

  // 文言 / 白话 切换
  langLabel() { return this.lang === 'plain' ? '看文言' : '白话译文'; },
  narrText(obj) {
    if (!obj) return '';
    if (this.lang === 'plain') return obj.narrative_plain || obj.narrative || '';
    return obj.narrative || obj.narrative_plain || '';
  },
  toggleLang() {
    this.lang = this.lang === 'plain' ? 'classic' : 'plain';
    document.getElementById('narrLang').textContent = this.langLabel();
    if (this.lastRes && !document.getElementById('narrativeDrawer').hidden) this.showNarrative(this.lastRes);
    this.renderChronicle();
  },

  showNarrative(res) {
    this.lastRes = res;
    document.getElementById('narrLang').textContent = this.langLabel();
    const tag = this.lang === 'plain' ? '白话' : '文言';
    document.getElementById('narrTitle').textContent = `${this.reign(res.year)}（公元${res.year}年） · 推演纪事〔${tag}〕`;
    const evs = (res.events || []).map(e => `<li>${e}</li>`).join('');
    const chips = Object.entries(res.changes || {}).map(([k, d]) => {
      const f = this.fac(k); const name = f ? f.name : k;
      const parts = Object.entries(d).filter(([kk, vv]) => kk !== 'note' && Math.abs(vv) >= 0.05)
        .map(([kk, vv]) => `${this.statName(kk)}${vv > 0 ? '+' : ''}${vv}`);
      if (!parts.length) return '';
      return `<span class="chip"><b>${name}</b> ${parts.join(' · ')}</span>`;
    }).join('');
    document.getElementById('narrBody').innerHTML = `
      <p class="narr-text">${this.narrText(res) || '（无叙事）'}</p>
      ${evs ? `<div class="narr-block"><h4>本年大事</h4><ul class="evlist">${evs}</ul></div>` : ''}
      ${chips ? `<div class="narr-block"><h4>国势变动（本年即时）</h4><div class="changes-grid">${chips}</div></div>` : ''}
      ${this.ongoingChips(res.ongoing)}
      ${res.difficulty ? `<div class="narr-block"><h4>施政评议</h4><p>${res.difficulty}</p></div>` : ''}
      ${res.verdict ? `<div class="verdict">${res.verdict}</div>` : ''}`;
    document.getElementById('narrativeDrawer').hidden = false;
  },

  ongoingChips(ongoing) {
    const o = ongoing || {};
    const parts = Object.entries(o).filter(([, v]) => Math.abs(v) >= 0.05)
      .map(([k, v]) => `<span class="chip"><b>${this.statName(k)}</b>${v > 0 ? '+' : ''}${v}</span>`).join('');
    if (!parts) return '';
    return `<div class="narr-block"><h4>现行国策续效（公式自动累计·随年衰减）</h4>
      <div class="changes-grid">${parts}</div></div>`;
  },

  statName(k) {
    return ({ treasury: '国库', population: '人口', economy: '经济', military: '军力',
      army: '兵力', tech: '科技', stability: '稳定', welfare: '民生', relation: '外交',
      science: '科技点' })[k] || k;
  },

  fmtMonths(m) {
    if (!isFinite(m) || m <= 0) return '—';
    m = Math.ceil(m);
    if (m < 12) return `约 ${m} 个月`;
    const y = Math.floor(m / 12), mo = m % 12;
    return `约 ${y} 年${mo ? ' ' + mo + ' 月' : ''}`;
  },

  async renderChronicle() {
    const hist = await API.history();
    const el = document.getElementById('pane-chronicle');
    if (!hist.length) { el.innerHTML = '<p class="muted">尚无史册。颁布政策、推演本回合后，纪事将载录于此。</p>'; return; }
    const bar = `<div class="chron-bar">
      <span>史册（${this.lang === 'plain' ? '白话' : '文言'}）</span>
      <span class="chron-bar-btns">
        ${this.state.turn > 0 ? '<button class="btn ghost sm chron-rewind" data-turn="0">↩ 回到开局</button>' : ''}
        <button class="btn ghost sm" id="chronLang">${this.langLabel()}</button>
      </span></div>`;
    const cur = this.state.turn;
    const items = hist.slice().reverse().map(h => {
      const evs = (h.events || []).map(e => `<li>${e}</li>`).join('');
      const canRewind = h.turn < cur;
      return `<div class="chron-item">
        <div class="chron-date">${this.reign(h.year)}（公元${h.year}年）　第${h.turn}回合　〔${h.provider}〕
          ${canRewind ? `<button class="btn ghost sm chron-rewind" data-turn="${h.turn}">↩ 回到此回合</button>` : '<span class="chron-now">▶ 当前</span>'}</div>
        <div class="chron-policy"><b>诏令：</b>${this.esc(h.policy || '萧规曹随').replace(/\n/g, '　')}</div>
        <div class="chron-narr">${this.narrText(h) || ''}</div>
        ${evs ? `<ul class="chron-ev">${evs}</ul>` : ''}
      </div>`;
    }).join('');
    el.innerHTML = bar + `<div class="chron">${items}</div>`;
    document.getElementById('chronLang').onclick = () => this.toggleLang();
    el.querySelectorAll('.chron-rewind').forEach(b =>
      b.onclick = () => this.doRewind(+b.dataset.turn));
  },

  async doRewind(turn) {
    if (!confirm(`回到第 ${turn} 回合？\n此后的所有回合记录将被舍弃（不可恢复），世界将从该回合重新演化。\n如需保留当前进度，请先「💾 存档」。`)) return;
    await API.rewind(turn);
    this.prev = {}; this.lastRes = null;
    document.getElementById('narrativeDrawer').hidden = true;
    await this.refresh();
    this.switchTab('state');
  },

  switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('.tabpane').forEach(p => p.classList.toggle('active', p.id === 'pane-' + name));
    if (name === 'tech') this.renderTech();
  },

  // ---- 科技树 ----
  async renderTech() {
    const el = document.getElementById('pane-tech');
    let t;
    try { t = await API.tech(); } catch { el.innerHTML = '<p class="muted">科技信息加载失败。</p>'; return; }
    const cur = t.techs.find(x => x.id === t.current);
    const pct = cur ? Math.min(100, (t.progress / cur.cost) * 100) : 0;
    const eta = cur && t.rate > 0 ? `约 ${Math.ceil((cur.cost - t.progress) / t.rate)} 年` : '—';
    const rateStr = `每年 <b>+${t.rate}</b>` +
      (t.policy_bonus ? `<span class="rate-bd">（基础 ${t.base_rate} ${t.policy_bonus > 0 ? '＋' : '－'}${Math.abs(t.policy_bonus)} 国策）</span>` : '');
    const head = `<div class="tech-head">
      <div>科技点 累计 <b>${t.science}</b> · ${rateStr}</div>
      ${cur ? `<div class="tech-cur">研究中：<b>${cur.name}</b> ${Math.round(t.progress)}/${cur.cost} · 预计 ${eta}
        <div class="bar"><span style="width:${pct}%"></span></div></div>`
        : '<div class="tech-cur muted">未选研究方向，点下方可研科技开始（基础科研缓慢，可颁兴学/科研之策加速）</div>'}</div>`;
    const effStr = e => Object.entries(e).map(([k, v]) => `${this.statName(k)}+${v}`).join(' ');
    const eras = t.eras.map(era => {
      const items = t.techs.filter(x => x.era === era).map(x => {
        let cls = x.status === 'done' ? 'done' : (x.status === 'available' ? 'avail' : 'locked');
        if (x.id === t.current) cls += ' current';
        const tag = x.status === 'done' ? '✓已研' : (x.id === t.current ? '研究中'
          : (x.status === 'available' ? '可研 ' + x.cost : '🔒' + x.cost));
        return `<div class="tech-card ${cls}" data-id="${x.id}" data-status="${x.status}">
          <div class="tc-top"><span class="tc-name">${x.name}</span><span class="tc-tag">${tag}</span></div>
          <div class="tc-blurb">${x.blurb}</div>
          <div class="tc-eff">效果：${effStr(x.effect)}</div></div>`;
      }).join('');
      return `<div class="tech-era"><div class="tech-era-h">${era}</div><div class="tech-grid">${items}</div></div>`;
    }).join('');
    el.innerHTML = head + eras;
    el.querySelectorAll('.tech-card[data-status="available"]').forEach(c =>
      c.onclick = async () => { await API.setResearch(c.dataset.id); this.renderTech(); });
  },

  // ---- 开战 / 战役结算 ----
  openWar(key) {
    const f = this.fac(key), song = this.fac('song');
    if (!f || !song) return;
    this.warTarget = key;
    document.getElementById('warTitle').textContent = `出兵讨伐 ${f.name}`;
    document.getElementById('warInfo').innerHTML =
      `<div class="war-cmp"><span>大宋</span><b>${Math.round(song.military)}</b><span>军力</span><b>${Math.round(f.military)}</b><span>${f.name}</span></div>
       <div class="war-sub">宋 兵力${Math.round(song.army)}万·科技${Math.round(song.tech)}　│　${f.name} 兵力${Math.round(f.army)}万·科技${Math.round(f.tech)}·守土有利</div>`;
    const ci = document.getElementById('warCommit');
    ci.value = Math.round(song.army * 0.6);
    ci.max = Math.round(song.army);
    ci.oninput = () => this.warEstimate();
    document.getElementById('warIntensity').value = 'battle';
    document.getElementById('warReport').innerHTML = '';
    document.getElementById('warModal').hidden = false;
    this.warEstimate();
  },
  warEstimate() {
    const song = this.fac('song'), foe = this.fac(this.warTarget);
    if (!song || !foe) return;
    const commit = Math.max(0, +document.getElementById('warCommit').value);
    const mine = song.army > 0 ? commit / song.army * song.military : 0;  // 投入战力
    const theirs = foe.military * 1.25;                                   // 守军(含守土+25%)
    const r = mine + theirs > 0 ? mine / (mine + theirs) : 0;
    const verdict = r > 0.58 ? ['胜算大', 'pos'] : r >= 0.45 ? ['胜负难料', ''] : ['凶多吉少', 'neg'];
    document.getElementById('warEstimate').innerHTML =
      `预计投入战力 <b>${mine.toFixed(0)}</b> vs 守军 <b>${theirs.toFixed(0)}</b>（含守土+25%）
       <b class="${verdict[1]}">${verdict[0]}</b>（约${Math.round(r * 100)}%）
       <div class="war-hint">提示：宋军重在数量，质量偏弱，宜以优势兵力进攻；守方有地利。</div>`;
  },
  async doWar() {
    const body = {
      faction: this.warTarget,
      commit_army: Math.max(1, +document.getElementById('warCommit').value),
      intensity: document.getElementById('warIntensity').value,
    };
    const btn = document.getElementById('warConfirm');
    btn.disabled = true;
    try {
      const r = await API.war(body);
      const cls = r.win_ratio >= 0.52 ? 'pos' : (r.win_ratio < 0.45 ? 'neg' : '');
      document.getElementById('warReport').innerHTML = `
        <div class="war-result ${cls}">战果：${r.outcome}（胜率 ${Math.round(r.win_ratio * 100)}%）${r.occupied ? ' · <b>敌军覆灭，已被占领！</b>' : ''}</div>
        <div class="war-stat">战力对比 宋 ${r.cp_song} vs ${r.target} ${r.cp_foe}</div>
        <div class="war-stat">我军折损 <b class="neg">${r.song_losses}万</b>（余 ${r.song_army}万）· 军费 <b class="neg">${r.war_cost}万贯</b></div>
        <div class="war-stat">敌军折损 <b class="pos">${r.foe_losses}万</b>（余 ${r.foe_army}万）· 敌军力降至 ${r.foe_military}</div>
        ${r.occupied ? '<div class="war-stat">可在「议和」中索取割地赔款，或继续推演以巩固。</div>' : ''}`;
      await this.refresh();
      this.switchTab('powers');
    } catch (e) {
      document.getElementById('warReport').innerHTML = `<div class="war-result neg">出兵失败：${e.message}</div>`;
    } finally { btn.disabled = false; }
  },

  // ---- 议和 ----
  openPeace(key) {
    const f = this.fac(key);
    if (!f) return;
    this.peaceTarget = key;
    document.getElementById('peaceTitle').textContent = `与 ${f.name} 议和`;
    document.getElementById('peaceInfo').innerHTML =
      `${f.name}：军力 ${Math.round(f.military)} · 国库 ${Math.round(f.treasury)} · 对宋 ${Math.round(f.relation)}` +
      (f.occupied ? ' · <b style="color:var(--bad)">已被占领</b>' : '');
    document.getElementById('peaceCede').value = f.occupied ? 60 : 20;
    document.getElementById('peaceIndem').value = 300;
    document.getElementById('peacePays').value = 'enemy';
    document.getElementById('peaceModal').hidden = false;
  },
  async doPeace() {
    const songPays = document.getElementById('peacePays').value === 'song';
    const body = {
      faction: this.peaceTarget,
      cede_fraction: Math.max(0, Math.min(90, +document.getElementById('peaceCede').value)) / 100,
      indemnity: Math.max(0, +document.getElementById('peaceIndem').value),
      song_pays: songPays,
    };
    try {
      const r = await API.peace(body);
      document.getElementById('peaceModal').hidden = true;
      await GameMap.loadFactions();   // 领土已变，重绘地图
      await this.refresh();
      alert(`议和达成：${songPays ? '大宋' : this.fac(this.peaceTarget)?.name || '对方'}割地 ${Math.round(r.area_moved * 100)}%、赔款 ${r.indemnity} 万贯。`);
    } catch (e) { alert('议和失败：' + e.message); }
  },

  // ---- evolution video ----
  async exportVideo() {
    const btn = document.getElementById('btnVideo');
    const old = btn.textContent;
    btn.disabled = true; btn.textContent = '🎬 生成中…';
    try {
      const r = await fetch('/api/video', { method: 'POST' });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || ('HTTP ' + r.status)); }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'dasong_evolution.mp4';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('生成视频失败：' + e.message);
    } finally {
      btn.disabled = false; btn.textContent = old;
    }
  },

  // ---- saves ----
  async openSaves() {
    document.getElementById('saveName').value = '';
    document.getElementById('savesModal').hidden = false;
    await this.renderSaves();
  },
  async renderSaves() {
    const saves = await API.listSaves();
    const el = document.getElementById('savesList');
    if (!saves.length) { el.innerHTML = '<p class="muted">暂无存档。</p>'; return; }
    el.innerHTML = saves.map(s => `
      <div class="save-row">
        <div class="save-meta">
          <div class="save-name">${this.esc(s.name)}</div>
          <div class="save-sub">${this.reign(s.year)}（公元${s.year}年） · 第${s.turn}回合 · ${(s.created_at || '').replace('T', ' ')}</div>
        </div>
        <div class="save-btns">
          <button class="btn primary sm" data-load="${s.id}">读取</button>
          <button class="btn ghost sm" data-del="${s.id}">删除</button>
        </div>
      </div>`).join('');
    el.querySelectorAll('[data-load]').forEach(b => b.onclick = () => this.doLoad(+b.dataset.load));
    el.querySelectorAll('[data-del]').forEach(b => b.onclick = () => this.doDelete(+b.dataset.del));
  },
  esc(s) { return (s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); },
  async doSave() {
    await API.createSave(document.getElementById('saveName').value);
    document.getElementById('saveName').value = '';
    await this.renderSaves();
  },
  async doLoad(id) {
    if (!confirm('读取该存档将覆盖当前进度，确定？')) return;
    await API.loadSave(id);
    document.getElementById('savesModal').hidden = true;
    this.prev = {}; this.selected = 'song';
    await this.refresh();
  },
  async doDelete(id) {
    if (!confirm('删除该存档？此操作不可恢复。')) return;
    await API.deleteSave(id);
    await this.renderSaves();
  },

  // ---- config modal ----
  bindConfigModal() {
    document.getElementById('cfgCancel').onclick = () => document.getElementById('configModal').hidden = true;
    document.getElementById('cfgSave').onclick = () => this.saveConfig();
  },
  openConfig() {
    const c = this.config;
    document.getElementById('cfgProvider').value = c.provider;
    document.getElementById('cfgModel').value = c.model || '';
    document.getElementById('cfgKey').value = '';
    document.getElementById('cfgKey').placeholder = c.has_key ? '已存密钥，留空则不修改' : '请输入 API Key';
    document.getElementById('cfgBase').value = c.base_url || '';
    document.getElementById('cfgTemp').value = c.temperature ?? 0.8;
    document.getElementById('cfgMaxTok').value = c.max_tokens ?? 4096;
    document.getElementById('cfgTimeout').value = c.timeout ?? 300;
    document.getElementById('configModal').hidden = false;
  },
  async saveConfig() {
    const body = {
      provider: document.getElementById('cfgProvider').value,
      model: document.getElementById('cfgModel').value,
      base_url: document.getElementById('cfgBase').value,
      temperature: parseFloat(document.getElementById('cfgTemp').value),
      max_tokens: parseInt(document.getElementById('cfgMaxTok').value),
      timeout: parseFloat(document.getElementById('cfgTimeout').value),
    };
    const key = document.getElementById('cfgKey').value.trim();
    if (key) body.api_key = key;
    this.config = await API.setConfig(body);
    this.renderProvider();
    document.getElementById('configModal').hidden = true;
  },

  async reset() {
    if (!confirm('确定重开棋局？所有推演进度（自熙宁元年起）将清空，回到 1068 年开局。')) return;
    await API.reset();
    this.prev = {}; this.selected = 'song';
    await GameMap.loadFactions();
    await this.refresh();
  },
};

window.addEventListener('DOMContentLoaded', () => UI.init());

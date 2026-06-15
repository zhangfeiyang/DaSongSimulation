// Leaflet world map: neutral country basemap + colored faction territories.
// 领土外观随战和/外交态势而变：交战者红虚线行军边、敌对者橙边、亲善者绿边、沦陷者灰化。
const GameMap = {
  map: null,
  factionLayer: null,
  labelLayer: null,
  statesByKey: {},
  layersByKey: {},
  propsByKey: {},
  onSelect: null,

  async init(onSelect) {
    this.onSelect = onSelect;
    this.map = L.map('map', {
      worldCopyJump: true,
      minZoom: 2, maxZoom: 8,
      center: [30, 95], zoom: 3,
      zoomControl: true, attributionControl: false,
    });

    // Neutral land basemap (high-res vector, no tiles -> works offline).
    const world = await fetch('/api/world.geojson').then(r => r.json());
    this._basemap = L.geoJSON(world, {
      style: { color: '#a69470', weight: 0.5, fillColor: '#e8dcc4', fillOpacity: 0.95 },
    }).addTo(this.map);
    // Coastline glow (subtle outer border for depth)
    this._coastGlow = L.geoJSON(world, {
      style: { color: '#8ba8b5', weight: 1.2, fillColor: 'transparent', fillOpacity: 0, opacity: 0.35 },
    }).addTo(this.map);

    this.labelLayer = L.layerGroup().addTo(this.map);
    this._injectStatusLegend();
    await this.loadFactions();
  },

  async loadFactions() {
    const gj = await fetch('/api/factions.geojson').then(r => r.json());
    if (this.factionLayer) this.map.removeLayer(this.factionLayer);
    const self = this;
    this.layersByKey = {};
    this.propsByKey = {};
    this.factionLayer = L.geoJSON(gj, {
      style: f => self._styleFor(f.properties),
      onEachFeature(feature, layer) {
        const key = feature.properties.key;
        self.layersByKey[key] = layer;
        self.propsByKey[key] = feature.properties;
        layer.on('mouseover', e => { layer.setStyle({ fillOpacity: 0.78, weight: 2.6 }); self.showTip(e, key); });
        layer.on('mousemove', e => self.moveTip(e));
        layer.on('mouseout', () => { self._restyle(key); self.hideTip(); });
        layer.on('click', () => self.onSelect && self.onSelect(key));
      },
    }).addTo(this.map);
    // Bring faction layer on top of basemap for crisp borders
    this.factionLayer.bringToFront();
    this.updateWarVisuals();
  },

  // ---- 领土视觉：随 at_war / relation / occupied / bankrupt 编码 ----
  _styleFor(p) {
    if (!p) return { color: '#888', weight: 1, fillOpacity: 0.3, dashArray: '' };
    const s = this.statesByKey[p.key];
    const baseFill = p.is_player ? 0.62 : 0.42;
    const base = { color: this._darken(p.color, 0.3), weight: 1.2, fillColor: p.color, fillOpacity: baseFill, dashArray: '' };
    if (!s) return base;
    if (s.occupied) {                                   // 沦陷：灰化、斜纹
      return { color: '#4a3328', weight: 1.4, fillColor: '#6e5f4e', fillOpacity: 0.26, dashArray: '3 5' };
    }
    if (s.at_war) {                                     // 交战：朱红粗虚线（边塞告急）
      return { color: '#e8261a', weight: 2.8, fillColor: p.color, fillOpacity: 0.58, dashArray: '8 4' };
    }
    if (s.relation <= -25) {                            // 敌对：橙边
      return { color: '#d06a1a', weight: 2, fillColor: p.color, fillOpacity: 0.5, dashArray: '' };
    }
    if (s.relation >= 50) {                             // 亲善：翠边
      return { color: '#2e7d6b', weight: 1.8, fillColor: p.color, fillOpacity: 0.48, dashArray: '' };
    }
    return base;
  },

  // darken a hex color for borders
  _darken(hex, amt) {
    if (!hex || hex[0] !== '#') return '#333';
    let r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    r = Math.max(0, Math.round(r * (1 - amt)));
    g = Math.max(0, Math.round(g * (1 - amt)));
    b = Math.max(0, Math.round(b * (1 - amt)));
    return '#' + [r,g,b].map(c => c.toString(16).padStart(2,'0')).join('');
  },

  _restyle(key) {
    const layer = this.layersByKey[key];
    if (!layer) return;
    layer.setStyle(this._styleFor(this.propsByKey[key]));
    const el = layer.getElement && layer.getElement();
    const s = this.statesByKey[key];
    if (el) el.classList.toggle('war-pulse', !!(s && s.at_war && !s.occupied));
  },

  // 依据当前 states 重绘所有领土外观与首都徽记（每回合 / 开战 / 议和后调用）
  updateWarVisuals() {
    Object.keys(this.layersByKey).forEach(k => this._restyle(k));
    this._renderStatusLegend();
  },

  setStates(states) {
    this.statesByKey = {};
    states.forEach(s => this.statesByKey[s.faction_key] = s);
    // 首都标签：交战者加 ⚔ 徽记
    this.labelLayer.clearLayers();
    states.forEach(s => {
      if (!s.capital) return;
      const [lat, lng] = s.capital.split(',').map(Number);
      const war = !s.is_player && !s.occupied && s.at_war;
      const sword = war ? '<b class="cap-sword">⚔</b>' : '';
      const icon = L.divIcon({
        className: 'cap-label',
        html: `<span class="cap-pill${war ? ' cap-war' : ''}" style="background:${s.color}">${sword}${s.name}</span>`,
        iconSize: [10, 10],
      });
      L.marker([lat, lng], { icon, interactive: false }).addTo(this.labelLayer);
    });
    this.updateWarVisuals();
  },

  // ---- 地图右上角的"天下态势"图例（动态统计交战/敌对数量）----
  _injectStatusLegend() {
    if (document.getElementById('mapStatus')) return;
    const el = document.createElement('div');
    el.id = 'mapStatus';
    el.className = 'map-status';
    document.getElementById('mapcol').appendChild(el);
  },

  _renderStatusLegend() {
    const el = document.getElementById('mapStatus');
    if (!el) return;
    const list = Object.values(this.statesByKey).filter(s => !s.is_player && !s.occupied);
    const wars = list.filter(s => s.at_war).length;
    const host = list.filter(s => !s.at_war && s.relation <= -25).length;
    const allies = list.filter(s => s.relation >= 50).length;
    el.innerHTML =
      `<div class="ms-title">天下态势${wars ? ' · <b class="ms-warn">烽烟未息</b>' : ' · 海宇承平'}</div>` +
      `<div class="ms-row"><span class="ms-sw war"></span>交战 <b>${wars}</b></div>` +
      `<div class="ms-row"><span class="ms-sw host"></span>敌对 <b>${host}</b></div>` +
      `<div class="ms-row"><span class="ms-sw ally"></span>亲善 <b>${allies}</b></div>` +
      `<div class="ms-row"><span class="ms-sw occ"></span>沦陷 <b>${list.filter(s=>false).length}</b></div>`;
  },

  showTip(e, key) {
    const s = this.statesByKey[key];
    if (!s) return;
    const tip = document.getElementById('tooltip');
    tip.hidden = false;
    const relCls = s.relation >= 0 ? '#3a8a4a' : '#c0392b';
    const tag = s.occupied ? '<span class="tip-tag occ">沦陷</span>'
              : s.at_war ? '<span class="tip-tag war">交战中</span>'
              : s.relation <= -25 ? '<span class="tip-tag host">敌对</span>'
              : s.relation >= 50 ? '<span class="tip-tag ally">亲善</span>' : '';
    tip.innerHTML = `<b>${s.name}</b> <span style="color:#ccc">${s.name_en || ''}</span> ${tag}<br>
      经济 ${Math.round(s.economy)} · 军力 ${Math.round(s.military)} · 科技 ${Math.round(s.tech)}<br>
      稳定 ${Math.round(s.stability)} · 民生 ${Math.round(s.welfare)} · 兵力 ${Math.round(s.army)}万<br>
      <span style="color:${relCls}">对宋外交 ${Math.round(s.relation)}</span>`;
    this.moveTip(e);
  },
  moveTip(e) {
    const tip = document.getElementById('tooltip');
    if (tip.hidden) return;
    const pt = e.originalEvent;
    const rect = document.getElementById('mapcol').getBoundingClientRect();
    let x = pt.clientX - rect.left + 14, y = pt.clientY - rect.top + 14;
    if (x + 250 > rect.width) x -= 270;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  },
  hideTip() { document.getElementById('tooltip').hidden = true; },

  flyTo(key) {
    const s = this.statesByKey[key];
    if (!s || !s.capital) return;
    const [lat, lng] = s.capital.split(',').map(Number);
    this.map.flyTo([lat, lng], 4, { duration: 0.6 });
  },
};

// inject small style for capital labels + war visuals
const _st = document.createElement('style');
_st.textContent = `
.cap-label span{display:inline-block;transform:translate(-50%,-50%);
  font-size:11px;color:#fff;padding:1px 6px;border-radius:10px;white-space:nowrap;
  border:1px solid rgba(255,255,255,.7);box-shadow:0 1px 3px rgba(0,0,0,.4);font-weight:600;}
.cap-label .cap-war{border-color:#ff6a55;box-shadow:0 0 0 2px rgba(232,38,26,.5),0 1px 4px rgba(0,0,0,.5);}
.cap-label .cap-sword{color:#ffe9e0;margin-right:3px;font-weight:400;animation:capThrob 1.1s ease-in-out infinite;display:inline-block;}
@keyframes capThrob{0%,100%{transform:scale(1)}50%{transform:scale(1.25)}}
.war-pulse{animation:warMarch .9s linear infinite;}
@keyframes warMarch{to{stroke-dashoffset:-12}}
.map-status{position:absolute;right:12px;top:12px;z-index:600;background:rgba(244,236,216,.95);
  border:1px solid var(--gold-2,#a07c2c);border-radius:9px;padding:7px 10px;font-size:11.5px;
  box-shadow:0 4px 16px rgba(40,28,15,.28);min-width:104px;}
.ms-title{font-weight:700;color:var(--vermilion-2,#8c1d17);margin-bottom:5px;letter-spacing:.5px;}
.ms-title .ms-warn{color:#c0392b;animation:capThrob 1.1s ease-in-out infinite;display:inline-block;}
.ms-row{display:flex;align-items:center;gap:6px;padding:1px 0;color:#4a3f38;}
.ms-row b{margin-left:auto;color:#1c1714;}
.ms-sw{width:14px;height:0;border-top:3px solid #888;border-radius:2px;display:inline-block;}
.ms-sw.war{border-top-style:dashed;border-color:#e8261a;border-width:3px;}
.ms-sw.host{border-color:#d06a1a;}
.ms-sw.ally{border-color:#2e7d6b;}
.ms-sw.occ{border-top-style:dotted;border-color:#6e5f4e;}
.tip-tag{font-size:10px;color:#fff;border-radius:7px;padding:0 6px;margin-left:4px;}
.tip-tag.war{background:#e8261a;} .tip-tag.host{background:#d06a1a;}
.tip-tag.ally{background:#2e7d6b;} .tip-tag.occ{background:#6b2020;}`;
document.head.appendChild(_st);

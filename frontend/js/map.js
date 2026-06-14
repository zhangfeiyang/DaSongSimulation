// Leaflet world map: neutral country basemap + colored faction territories.
const GameMap = {
  map: null,
  factionLayer: null,
  labelLayer: null,
  statesByKey: {},
  onSelect: null,

  async init(onSelect) {
    this.onSelect = onSelect;
    this.map = L.map('map', {
      worldCopyJump: true,
      minZoom: 2, maxZoom: 6,
      center: [30, 95], zoom: 3,
      zoomControl: true, attributionControl: false,
    });

    // Neutral land basemap (vector, no tiles -> works offline).
    const world = await fetch('/api/world.geojson').then(r => r.json());
    L.geoJSON(world, {
      style: { color: '#b7a988', weight: 0.6, fillColor: '#e9dcc0', fillOpacity: 1 },
    }).addTo(this.map);

    this.labelLayer = L.layerGroup().addTo(this.map);
    await this.loadFactions();
  },

  async loadFactions() {
    const gj = await fetch('/api/factions.geojson').then(r => r.json());
    if (this.factionLayer) this.map.removeLayer(this.factionLayer);
    const self = this;
    this.factionLayer = L.geoJSON(gj, {
      style: f => ({
        color: f.properties.color, weight: 1.5,
        fillColor: f.properties.color,
        fillOpacity: f.properties.is_player ? 0.62 : 0.42,
      }),
      onEachFeature(feature, layer) {
        const key = feature.properties.key;
        layer.on('mouseover', e => { layer.setStyle({ fillOpacity: 0.78, weight: 2.5 }); self.showTip(e, key); });
        layer.on('mousemove', e => self.moveTip(e));
        layer.on('mouseout', () => {
          layer.setStyle({ fillOpacity: feature.properties.is_player ? 0.62 : 0.42, weight: 1.5 });
          self.hideTip();
        });
        layer.on('click', () => self.onSelect && self.onSelect(key));
      },
    }).addTo(this.map);
  },

  setStates(states) {
    this.statesByKey = {};
    states.forEach(s => this.statesByKey[s.faction_key] = s);
    // capital labels
    this.labelLayer.clearLayers();
    states.forEach(s => {
      if (!s.capital) return;
      const [lat, lng] = s.capital.split(',').map(Number);
      const icon = L.divIcon({
        className: 'cap-label',
        html: `<span style="background:${s.color}">${s.name}</span>`,
        iconSize: [10, 10],
      });
      L.marker([lat, lng], { icon, interactive: false }).addTo(this.labelLayer);
    });
  },

  showTip(e, key) {
    const s = this.statesByKey[key];
    if (!s) return;
    const tip = document.getElementById('tooltip');
    tip.hidden = false;
    tip.innerHTML = `<b>${s.name}</b> <span style="color:#ccc">${s.name_en || ''}</span><br>
      经济 ${Math.round(s.economy)} · 军力 ${Math.round(s.military)} · 科技 ${Math.round(s.tech)}<br>
      稳定 ${Math.round(s.stability)} · 民生 ${Math.round(s.welfare)} · 兵力 ${Math.round(s.army)}万<br>
      <span style="color:#c9a24b">对宋外交 ${Math.round(s.relation)}</span>`;
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

// inject small style for capital labels
const _st = document.createElement('style');
_st.textContent = `.cap-label span{display:inline-block;transform:translate(-50%,-50%);
  font-size:11px;color:#fff;padding:1px 6px;border-radius:10px;white-space:nowrap;
  border:1px solid rgba(255,255,255,.7);box-shadow:0 1px 3px rgba(0,0,0,.4);font-weight:600;}`;
document.head.appendChild(_st);

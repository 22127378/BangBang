// M52: lobby event bar (top-right) + native-styled event panels for events-v1.
// The server builds every view; this module only renders it and sends ops.
import {createNativePanel} from './m81_native_panel.js';
import {nativeText} from './m8_ui_helpers.js';

const STYLE_ID = 'm81352-events-style';
const CURRENCY = {cash: 'Xu', golden: 'Bạc', gift: 'Xu khóa'};
// Icon per event: item icons that already exist in the garage catalog.
const EVENT_ICON = {351: 2600065, 350: 2003170, 309: 2600004, 990040: 3205525, 99124: 2000650,
  99036: 2003017, 99042: 2009038, 99016: 2200002, 99035: 2003022, 99007: 2001513};
// Scheduled competitions: distinct themed item icons (all present in the package).
const PERIODIC_ICON = {heat: 2004021, fun: 2004062, league: 2004034, team: 2004051, fire: 2001012, ball: 4712102, ladder: 2001017};
const CSS = `
.m81352-bar{position:absolute;right:8px;top:40px;display:flex;flex-direction:column;align-items:flex-end;gap:2px;z-index:30;pointer-events:none}
/* Fixed events: free floor strip above the bottom dock (top-right row 2 would cover the mode cards). */
.m81352-bar.m81352-bar2{top:auto;bottom:64px}
.m81352-line{display:flex;flex-direction:row;justify-content:flex-end;gap:4px}
.m81352-btn{pointer-events:auto;position:relative;width:54px;height:64px;padding:0;border:0;background:transparent;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;gap:2px;color:#fff;font:bold 10px/1.1 Tahoma,sans-serif;text-shadow:0 1px 2px #000,0 0 3px #003a5e}
.m81352-btn .m81352-ico{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;overflow:hidden;
  background:radial-gradient(circle at 35% 30%,#5fd0ff,#126bb0 60%,#0a3a66);border:2px solid #ffd24a;box-shadow:0 2px 5px #0008}
.m81352-btn .m81352-ico img{width:34px;height:34px;object-fit:contain}
.m81352-btn.m81352-boss .m81352-ico{background:radial-gradient(circle at 35% 30%,#ff8a5c,#a3220e 60%,#4a0b04)}
.m81352-btn.m81352-boss .m81352-ico img{width:44px;height:34px}
.m81352-btn:hover .m81352-ico,.m81352-btn:focus-visible .m81352-ico{filter:brightness(1.2);transform:scale(1.06)}
.m81352-btn:focus-visible{outline:none}
.m81352-btn span.m81352-name{max-width:58px;text-align:center;white-space:normal;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.m81352-btn.m81352-periodic .m81352-ico{background:radial-gradient(circle at 35% 30%,#ffd36b,#c26a08 60%,#5a2c02)}
.m81352-btn.m81352-live .m81352-ico{box-shadow:0 0 0 2px #fff6,0 0 10px 3px #ffe14a;animation:m81352-pulse 1.4s ease-in-out infinite}
@keyframes m81352-pulse{50%{box-shadow:0 0 0 2px #fff6,0 0 16px 6px #ffb300}}
.m81352-live-tag{position:absolute;left:50%;top:-6px;z-index:1;transform:translateX(-50%);padding:0 4px;border-radius:6px;background:#e8261c;border:1px solid #fff;font:bold 8px/12px Tahoma,sans-serif;white-space:nowrap}
.m81352-desc{margin:0 0 8px;padding:8px 10px;border-radius:7px;background:#fff8;border:1px solid #6fb8e6;line-height:1.45}
.m81352-desc em{display:block;margin-top:4px;color:#a3460b;font-style:normal;font-weight:bold}
.m81352-pill{min-width:74px;padding:0 8px;height:26px;border-radius:13px;font:bold 12px/26px Tahoma,sans-serif;text-align:center;color:#fff;background:#7d8b96;white-space:nowrap}
.m81352-row[data-state=claimable] .m81352-pill{background:#1f9a3a;box-shadow:0 0 6px #4cff7a}
.m81352-row[data-state=claimable]{border-color:#2fb24f;background:linear-gradient(180deg,#eafff0,#c4f0d0)}
.m81352-badge{position:absolute;right:2px;top:-2px;min-width:16px;height:16px;padding:0 4px;border-radius:8px;background:#e8261c;border:1px solid #fff;
  font:bold 10px/14px Tahoma,sans-serif;color:#fff;box-sizing:border-box}
.m81352-shade{position:absolute;left:0;top:0;width:1018px;height:618px;z-index:60;background:#000a;display:flex;align-items:center;justify-content:center}
.m81352-title{position:absolute;left:0;right:0;top:9px;text-align:center;font:bold 18px Tahoma,sans-serif;color:#fff;text-shadow:0 0 3px #0a3d6b,0 2px 0 #0a3d6b;pointer-events:none}
.m81352-body{position:absolute;left:26px;right:26px;top:50px;bottom:96px;overflow-y:auto;padding-right:4px;color:#0b2d4d;font:12px Tahoma,sans-serif}
.m81352-section h4{margin:6px 0;font:bold 13px Tahoma,sans-serif;color:#0b3a66}
.m81352-row{display:flex;align-items:center;gap:8px;padding:6px 8px;margin-bottom:6px;border-radius:7px;background:linear-gradient(180deg,#e9f7ff,#c7e8fb);
  border:1px solid #6fb8e6;min-height:44px}
.m81352-row[data-state=claimed]{opacity:.6}
.m81352-text{flex:1;min-width:0}.m81352-text b{display:block;font-size:13px;color:#073a66}.m81352-text small{color:#2e5c80}
.m81352-rewards,.m81352-cost{display:flex;gap:4px;flex-wrap:wrap;align-items:center}
.m81352-chip{position:relative;width:40px;height:40px;border-radius:6px;background:#0d4f86;border:1px solid #8fd6ff;display:flex;align-items:center;justify-content:center}
.m81352-chip img{width:34px;height:34px;object-fit:contain}
.m81352-chip i{position:absolute;right:1px;bottom:0;font:bold 10px Tahoma,sans-serif;font-style:normal;color:#fff;text-shadow:0 1px 1px #000,0 0 2px #000}
.m81352-chip.m81352-cur{width:auto;min-width:40px;padding:0 6px;font:bold 11px Tahoma,sans-serif;color:#ffe27a;background:#7a4a05;border-color:#ffd24a}
.m81352-cost .m81352-chip{background:#5a1d12;border-color:#ff9a7a}
.m81352-act{min-width:74px;height:30px;border-radius:6px;border:1px solid #a86a00;cursor:pointer;font:bold 12px Tahoma,sans-serif;color:#2b1600;
  background:linear-gradient(180deg,#ffe58a,#f0a818);box-shadow:inset 0 1px 0 #fff8,0 1px 2px #0006}
.m81352-act:disabled{cursor:default;filter:grayscale(1);opacity:.55}
.m81352-act:not(:disabled):hover{filter:brightness(1.08)}
.m81352-footer{position:absolute;left:30px;right:30px;bottom:34px;min-height:20px;text-align:center;font:bold 13px Tahoma,sans-serif;color:#0b3a66}
.m81352-footer.err{color:#b3140b}
.m81352-wheel{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:4px 0 10px}
.m81352-cell{position:relative;height:92px;border-radius:8px;background:linear-gradient(180deg,#2a7fc4,#0e3f73);border:2px solid #8fd6ff;color:#fff;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;font:bold 10px Tahoma,sans-serif;text-align:center;padding:3px;box-sizing:border-box}
.m81352-cell img{width:44px;height:44px;object-fit:contain}
.m81352-cell.lucky{border-color:#ff7ad1}
.m81352-cell.on{border-color:#ffd24a;box-shadow:0 0 0 3px #ffb300,0 0 14px #ffd24a;background:linear-gradient(180deg,#3a92d6,#14508c)}
.m81352-ph{display:flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;background:#ffd24a;color:#5a2a00;font:bold 12px Tahoma,sans-serif;text-shadow:none}
.m81352-cell .m81352-ph{width:44px;height:44px;font-size:15px}
.m81352-wheelbar{display:flex;align-items:center;justify-content:center;gap:10px;font:bold 13px Tahoma,sans-serif;color:#0b3a66}
`;

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style'); style.id = STYLE_ID; style.textContent = CSS; document.head.append(style);
}
const initials = name => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
const el = (tag, cls = '', text = null) => {
  const node = document.createElement(tag); if (cls) node.className = cls; if (text != null) node.textContent = text; return node;
};

export class EventsUI {
  constructor(ui) { this.ui = ui; this.bar = null; this.shade = null; this.openId = null; this.revision = -1; this.timer = null; this.spinning = null; }
  get state() { return this.ui.state?.events; }
  view(id) { return (this.state?.views || []).find(v => v.id === id) || null; }
  icon(itemId) {
    const definition = this.ui.assets?.garage?.items?.[itemId], asset = definition?.icon && this.ui.assets.get?.(definition.icon);
    if (!asset?.url) return null;
    const image = el('img'); image.alt = ''; image.draggable = false; image.src = asset.url;
    image.addEventListener('error', () => image.replaceWith(el('span', 'm81352-ph', '•'))); return image;
  }
  /** Item art missing from the package: a short-name badge instead of "?". */
  placeholder(reward) {
    const words = this.rewardName(reward).replace(/[^\p{L}\p{N} ]/gu, ' ').trim().split(/\s+/).filter(Boolean);
    const digits = words.find(w => /^\d+$/.test(w));
    return el('span', 'm81352-ph', digits ? digits.slice(0, 4) : words.slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?');
  }
  firstIcon(ids = []) {
    for (const id of ids) { const image = this.icon(id); if (image) return image; }
    return null;
  }
  rewardName(reward) {
    if (reward.kind === 'currency') return CURRENCY[reward.id] || reward.id;
    if (reward.kind === 'tank') return 'Tank ' + nativeText(this.ui.assets.tankName?.(reward.id) || '');
    return nativeText(this.ui.assets?.garage?.items?.[reward.id]?.name || `Vật phẩm ${reward.id}`);
  }
  chip(reward) {
    if (reward.kind === 'currency') {
      const chip = el('span', 'm81352-chip m81352-cur', `${reward.quantity} ${CURRENCY[reward.id] || ''}`); chip.title = this.rewardName(reward); return chip;
    }
    const chip = el('span', 'm81352-chip'); chip.title = `${this.rewardName(reward)} x${reward.quantity}`;
    let image = null;
    if (reward.kind === 'tank') {
      const micro = this.ui.assets?.garage?.tanks?.[reward.id]?.microIcon, asset = micro && this.ui.assets.get?.(micro);
      if (asset?.url) { image = el('img'); image.src = asset.url; image.alt = ''; }
    } else image = this.icon(reward.id);
    chip.append(image || this.placeholder(reward));
    if (reward.quantity > 1) chip.append(el('i', '', `x${reward.quantity}`));
    return chip;
  }

  /** Lobby: build the top-right event bar (boss first, then every event). */
  mount() {
    ensureStyle();
    this.bar = el('div', 'm81352-bar'); this.bar.setAttribute('role', 'toolbar'); this.bar.setAttribute('aria-label', 'Sự kiện định kỳ');
    this.bar2 = el('div', 'm81352-bar m81352-bar2'); this.bar2.setAttribute('role', 'toolbar'); this.bar2.setAttribute('aria-label', 'Sự kiện cố định');
    this.ui.content.append(this.bar, this.bar2);
    this.revision = -1; this.renderBar();
    this.ui.client.eventsList?.().catch(() => {});
    clearInterval(this.timer);
    // Online-time events count minutes while the lobby is open.
    this.timer = setInterval(() => {
      if (this.ui.screen === 'lobby' && this.ui.state?.phase === 'ready' && this.ui.state.play?.phase === 'lobby')
        this.ui.client.eventsList?.().catch(() => {});
    }, 60000);
  }
  renderBar() {
    if (!this.bar?.isConnected) return;
    const button = (cls, label, onClick, image, badge) => {
      const node = el('button', 'm81352-btn ' + cls); node.type = 'button'; node.title = label; node.setAttribute('aria-label', label);
      const ico = el('span', 'm81352-ico'); if (image) ico.append(image);
      node.append(ico, el('span', 'm81352-name', label));
      if (badge > 0) node.append(el('span', 'm81352-badge', String(Math.min(badge, 99))));
      node.addEventListener('click', onClick); return node;
    };
    const boss = this.ui.assets.get?.('zh_CN/gui_summer/controls/main/worldBoss.png');
    const bossImage = boss?.url ? Object.assign(el('img'), {src: boss.url, alt: ''}) : null;
    // Row 1: scheduled competitions (Kẻ Hủy Diệt first). Row 2: fixed events.
    const periodic = [button('m81352-boss', 'Kẻ Hủy Diệt', () => this.ui.navigate('worldboss'), bossImage, 0)], fixed = [];
    periodic[0].dataset.testid = 'm52-event-boss';
    for (const view of this.state?.views || []) {
      const isPeriodic = view.group === 'periodic';
      const image = isPeriodic ? this.firstIcon([PERIODIC_ICON[view.slug], ...(view.icons || [])]) : this.icon(EVENT_ICON[view.id]);
      const node = button(isPeriodic ? 'm81352-periodic' + (view.live ? ' m81352-live' : '') : '', view.name,
        () => this.open(view.id), image || (isPeriodic ? el('span', 'm81352-ph', initials(view.name)) : null), view.badge);
      if (view.live) node.append(el('span', 'm81352-live-tag', 'ĐANG MỞ'));
      node.dataset.testid = `m52-event-${view.slug || view.id}`; (isPeriodic ? periodic : fixed).push(node);
    }
    const line = nodes => { const row = el('div', 'm81352-line'); row.append(...nodes); return row; };
    this.bar.replaceChildren(line(periodic));
    this.bar2?.replaceChildren(...(fixed.length ? [line(fixed)] : []));
  }
  update() {
    const revision = this.state?.revision ?? -1;
    if (revision === this.revision) return;
    this.revision = revision; this.renderBar();
    if (this.openId != null && this.shade?.isConnected && !this.spinning) this.renderPanel();
  }
  dispose() { clearInterval(this.timer); this.timer = null; this.shade?.remove(); this.shade = null; this.openId = null; }

  open(id) {
    this.shade?.remove(); this.openId = id; this.message = ''; this.error = false;
    const shade = el('div', 'm81352-shade'); shade.setAttribute('role', 'dialog'); shade.setAttribute('aria-modal', 'true');
    const close = () => { shade.remove(); this.shade = null; this.openId = null; };
    let panel;
    try {
      panel = createNativePanel({assets: {...this.ui.assets.ui.assets, ...this.ui.assets.panels.assets}, width: 800, height: 560,
        kind: 'box1', state: 'CONFIRM', close: {asset: 'public.close', x: 746, y: 15, label: 'Đóng'}, onClose: close});
    } catch { panel = {root: el('div'), content: null}; Object.assign(panel.root.style, {width: '800px', height: '560px', background: '#5db8e9', borderRadius: '12px'}); }
    panel.root.style.position = 'relative';
    this.panelBody = panel.content || panel.root;
    shade.append(panel.root);
    shade.addEventListener('click', event => { if (event.target === shade) close(); });
    shade.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } });
    this.shade = shade; this.ui.content.append(shade);
    this.renderPanel();
    this.ui.client.eventsList?.().catch(() => {});
  }
  async perform(op, key = '') {
    try {
      const reply = await this.ui.client.eventsAct(this.openId, op, key);
      const result = reply?.result;
      const got = (result?.granted || []).map(r => `${this.rewardName(r)} x${r.quantity}`).join(', ');
      this.message = (result?.message || 'Hoàn tất.') + (got ? ` Nhận: ${got}.` : ''); this.error = false;
      return reply;
    } catch (error) { this.message = error.message; this.error = true; this.renderPanel(); return null; }
  }
  renderPanel() {
    const view = this.view(this.openId); if (!this.panelBody) return;
    const title = el('div', 'm81352-title', view?.name || 'Sự kiện');
    const body = el('div', 'm81352-body'), footer = el('div', 'm81352-footer' + (this.error ? ' err' : ''), this.message || '');
    if (!view) body.append(el('p', '', 'Đang tải dữ liệu sự kiện…'));
    else {
      if (view.desc) {
        const desc = el('p', 'm81352-desc', view.desc); if (view.note) desc.append(el('em', '', view.note)); body.append(desc);
      }
      if (view.roulette) body.append(this.renderWheel(view.roulette));
      for (const section of view.sections || []) {
        const box = el('div', 'm81352-section'); box.append(el('h4', '', section.title || ''));
        for (const row of section.rows) {
          const line = el('div', 'm81352-row'); line.dataset.state = row.state;
          const rewards = el('div', 'm81352-rewards'); for (const reward of row.rewards) rewards.append(this.chip(reward));
          const text = el('div', 'm81352-text'); text.append(el('b', '', row.title)); if (row.sub) text.append(el('small', '', row.sub));
          const cost = el('div', 'm81352-cost'); for (const c of row.cost || []) cost.append(this.chip(c));
          let act;
          if (!row.button.op && view.group === 'periodic') act = el('span', 'm81352-pill', row.button.label);  // schedule status only
          else {
            act = el('button', 'm81352-act', row.state === 'claimed' ? 'Đã xong' : row.button.label);
            act.type = 'button'; act.disabled = !row.button.enabled;
            act.addEventListener('click', () => this.perform(row.button.op, row.key));
          }
          act.dataset.testid = `m52-act-${row.key}`;
          line.append(rewards, text, cost, act); box.append(line);
        }
        body.append(box);
      }
    }
    const keep = this.panelBody.querySelector('.m81352-body')?.scrollTop || 0;
    for (const node of [...this.panelBody.querySelectorAll('.m81352-title,.m81352-body,.m81352-footer')]) node.remove();
    this.panelBody.append(title, body, footer); body.scrollTop = keep;
  }
  renderWheel(wheel) {
    const box = el('div', 'm81352-section');
    const grid = el('div', 'm81352-wheel');
    wheel.cells.forEach((cell, index) => {
      const node = el('div', 'm81352-cell' + (cell.lucky ? ' lucky' : '')); node.dataset.index = String(index); node.dataset.cell = String(cell.id);
      const reward = {kind: 'item', id: cell.item, quantity: cell.quantity};
      node.append(this.icon(cell.item) || this.placeholder(reward), el('span', '', `${this.rewardName(reward)}${cell.quantity > 1 ? ' x' + cell.quantity : ''}`));
      node.title = this.rewardName(reward);
      if (cell.id === wheel.last) node.classList.add('on');
      grid.append(node);
    });
    const bar = el('div', 'm81352-wheelbar');
    bar.append(el('span', '', `${wheel.ticketName}: ${wheel.tickets}`));
    const button = (label, op, enabled, id) => { const b = el('button', 'm81352-act', label); b.type = 'button'; b.disabled = !enabled; b.dataset.testid = id;
      b.addEventListener('click', () => op === 'spin' ? this.spin(grid) : this.perform(op)); return b; };
    bar.append(button('Nhận vé hôm nay', 'free_ticket', wheel.freeReady, 'm52-free-ticket'),
      button(`Mua vé (${wheel.ticketPrice} Xu)`, 'buy_ticket', true, 'm52-buy-ticket'),
      button('Quay', 'spin', wheel.tickets > 0, 'm52-spin'));
    box.append(grid, bar); return box;
  }
  async spin(grid) {
    if (this.spinning) return;
    const cells = [...grid.children]; let index = 0;
    for (const b of this.panelBody.querySelectorAll('.m81352-wheelbar button')) b.disabled = true;
    this.spinning = setInterval(() => { cells.forEach(c => c.classList.remove('on')); cells[index++ % cells.length].classList.add('on'); }, 70);
    const reply = await this.perform('spin');
    const target = reply ? (this.view(this.openId)?.roulette?.last) : null;
    const stopAt = cells.findIndex(c => Number(c.dataset.cell) === target);
    // Decelerate to the server-chosen cell (display only; the server drew it).
    clearInterval(this.spinning);
    let step = 0, delay = 80, current = index;
    const land = () => {
      cells.forEach(c => c.classList.remove('on'));
      cells[current % cells.length].classList.add('on');
      if (stopAt < 0 || (step > 8 && current % cells.length === stopAt)) { this.spinning = null; this.renderPanel(); return; }
      current++; step++; delay += 25; setTimeout(land, delay);
    };
    land();
  }
}

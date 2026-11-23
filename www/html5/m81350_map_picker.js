// M50: native-styled map picker panel (replaces the plain <select> boxes).
// Cards follow the waiting-room palette: blue native box1 panel, deep-blue
// cards, gold selection frame. "Ngẫu nhiên" is always the last card.
import {createNativePanel} from './m81_native_panel.js';
import {BATTLE_MAPS, RANDOM_MODE} from './m810_modes.js';

const STYLE_ID = 'm81350-map-picker-style';
const CSS = `
.m81350-shade{position:absolute;left:0;top:0;width:1018px;height:618px;z-index:60;background:#000a;display:flex;align-items:center;justify-content:center}
.m81350-panel{position:relative}
.m81350-title{position:absolute;left:0;right:0;top:9px;text-align:center;font:bold 18px Tahoma,sans-serif;color:#fff;
  text-shadow:0 0 3px #0a3d6b,0 2px 0 #0a3d6b;letter-spacing:1px;pointer-events:none}
.m81350-grid{position:absolute;left:24px;top:52px;right:24px;bottom:92px;display:grid;grid-template-columns:repeat(6,1fr);gap:8px;
  overflow-y:auto;padding:4px;align-content:start}
.m81350-card{position:relative;display:flex;flex-direction:column;align-items:stretch;padding:4px 4px 5px;height:100px;border-radius:7px;cursor:pointer;
  background:linear-gradient(180deg,#2a7fc4,#0e3f73);border:2px solid #8fd6ff;box-shadow:inset 0 1px 0 #ffffff55,0 2px 4px #0005;color:#fff;
  font:12px Tahoma,sans-serif;text-align:center;transition:transform .08s,box-shadow .12s}
.m81350-card:hover,.m81350-card:focus-visible{transform:translateY(-2px);border-color:#fff3b0;box-shadow:0 0 0 2px #ffd24a88,0 4px 8px #0006;outline:none}
.m81350-card[aria-pressed=true]{border-color:#ffd24a;box-shadow:0 0 0 3px #ffb300,0 0 12px #ffd24a;background:linear-gradient(180deg,#3a92d6,#14508c)}
.m81350-thumb{height:54px;border-radius:4px;background:#0a2440 center/cover no-repeat;border:1px solid #06203a;overflow:hidden}
.m81350-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.m81350-name{margin-top:4px;font-weight:bold;line-height:1.15;text-shadow:0 1px 2px #000;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.m81350-group{position:absolute;left:6px;top:6px;padding:1px 5px;border-radius:3px;font:bold 9px Tahoma,sans-serif;color:#fff;text-shadow:0 1px 1px #000}
.m81350-card[data-group="PK"] .m81350-group{background:#d9472b}
.m81350-card[data-group="Phá trụ"] .m81350-group{background:#7a4cc2}
.m81350-card[data-group="Chiếm cứ điểm"] .m81350-group{background:#1f9a5a}
.m81350-card[data-group="Hộ tống"] .m81350-group{background:#c77a12}
.m81350-card[data-group="Sinh tử"] .m81350-group{background:#8c1d2a}
.m81350-card[data-group="Luyện tập"] .m81350-group{background:#4d6b80}
.m81350-random .m81350-thumb{display:flex;align-items:center;justify-content:center;font:bold 40px Tahoma,sans-serif;color:#ffe27a;
  background:radial-gradient(circle,#ffb300 0%,#c25a00 55%,#5a2400 100%);text-shadow:0 2px 0 #7a3c00,0 0 8px #000}
.m81350-random{background:linear-gradient(180deg,#e09a1c,#8a4a05);border-color:#ffe08a}
.m81350-footer{position:absolute;left:30px;right:30px;bottom:30px;text-align:center;font:13px Tahoma,sans-serif;color:#0b3a66;font-weight:bold}
.m81350-trigger{display:flex;align-items:center;gap:8px;width:100%;min-height:44px;padding:3px 8px 3px 3px;border-radius:6px;cursor:pointer;
  background:linear-gradient(180deg,#2a7fc4,#0e3f73);border:2px solid #8fd6ff;color:#fff;font:bold 13px Tahoma,sans-serif;text-align:left;text-shadow:0 1px 2px #000}
.m81350-trigger:hover,.m81350-trigger:focus-visible{border-color:#ffd24a;outline:none;box-shadow:0 0 0 2px #ffd24a88}
.m81350-trigger:disabled{opacity:.55;cursor:default}
.m81350-trigger .m81350-thumb{width:62px;height:36px;flex:0 0 62px}
.m81350-trigger .m81350-trigger-text{flex:1;line-height:1.2}
.m81350-trigger small{display:block;font-weight:normal;font-size:11px;color:#cfe9ff}
.m81350-room-change{position:absolute;cursor:pointer;border:2px solid transparent;border-radius:4px;background:transparent;padding:0}
.m81350-room-change:hover,.m81350-room-change:focus-visible{border-color:#ffd24a;box-shadow:0 0 10px #ffd24a;outline:none}
.m81350-room-change span{position:absolute;left:50%;bottom:4px;transform:translateX(-50%);white-space:nowrap;padding:2px 8px;border-radius:9px;
  font:bold 11px Tahoma,sans-serif;color:#2b1600;background:#ffd24ae6;border:1px solid #a86a00;box-shadow:0 1px 3px #0008}
`;

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID; style.textContent = CSS; document.head.append(style);
}

/** Ordered choices: every verified map, then the random option last. */
export function mapChoices({includePractice = false} = {}) {
  return [...BATTLE_MAPS.filter(row => includePractice || !row.mode.startsWith('test')), RANDOM_MODE];
}

export function choiceFor(mode) {
  return mapChoices({includePractice: true}).find(row => row.mode === mode) || RANDOM_MODE;
}

function thumb(assets, row) {
  const box = document.createElement('div'); box.className = 'm81350-thumb';
  if (row.mode === RANDOM_MODE.mode) { box.textContent = '?'; return box; }
  const preview = assets?.m3?.maps?.[String(row.mapId)]?.preview;
  if (preview?.url) {
    const image = document.createElement('img'); image.alt = ''; image.draggable = false;
    image.decoding = 'async'; image.src = preview.url; box.append(image);
  }
  return box;
}

/** Fill a trigger button with the current choice (thumbnail + name). */
export function paintMapTrigger(button, assets, mode) {
  ensureStyle();
  const row = choiceFor(mode);
  const text = document.createElement('span'); text.className = 'm81350-trigger-text';
  text.textContent = row.name;
  const sub = document.createElement('small'); sub.textContent = `${row.group} · bấm để chọn bản đồ`;
  text.append(sub);
  button.replaceChildren(thumb(assets, row), text);
  button.setAttribute('aria-label', `Bản đồ: ${row.name}. Bấm để chọn bản đồ khác`);
  button.dataset.mode = row.mode;
}

/** Open the picker inside host (the 1018x618 stage). Returns a close function. */
export function openMapPicker({host, assets, current = RANDOM_MODE.mode, includePractice = false,
  title = 'Chọn bản đồ', onPick}) {
  ensureStyle();
  const shade = document.createElement('div'); shade.className = 'm81350-shade';
  shade.setAttribute('role', 'dialog'); shade.setAttribute('aria-modal', 'true'); shade.setAttribute('aria-label', title);
  const previous = document.activeElement;
  const close = () => { shade.remove(); previous?.focus?.(); };
  let panel;
  try {
    panel = createNativePanel({assets: {...assets.ui.assets, ...assets.panels.assets}, width: 860, height: 590,
      kind: 'box1', state: 'CONFIRM', close: {asset: 'public.close', x: 806, y: 15, label: 'Đóng'}, onClose: close});
  } catch {
    panel = {root: document.createElement('div'), content: null};
    Object.assign(panel.root.style, {width: '860px', height: '590px', background: '#5db8e9', borderRadius: '12px', border: '3px solid #fff'});
  }
  panel.root.classList.add('m81350-panel');
  const body = panel.content || panel.root;
  const heading = document.createElement('div'); heading.className = 'm81350-title'; heading.textContent = title;
  const grid = document.createElement('div'); grid.className = 'm81350-grid'; grid.setAttribute('role', 'listbox');
  let selected = null;
  for (const row of mapChoices({includePractice})) {
    const card = document.createElement('button'); card.type = 'button';
    card.className = 'm81350-card' + (row.mode === RANDOM_MODE.mode ? ' m81350-random' : '');
    card.dataset.group = row.group; card.dataset.mode = row.mode;
    card.setAttribute('role', 'option'); card.dataset.testid = `m81350-map-${row.mode}`;
    const active = row.mode === current; card.setAttribute('aria-pressed', String(active));
    card.title = row.mode === RANDOM_MODE.mode ? 'Mỗi phòng server tự bốc một bản đồ' : `${row.group} · ${row.name}`;
    const group = document.createElement('span'); group.className = 'm81350-group'; group.textContent = row.group;
    const name = document.createElement('span'); name.className = 'm81350-name';
    name.textContent = row.mode === RANDOM_MODE.mode ? 'Ngẫu nhiên' : row.name;
    card.append(thumb(assets, row), name);
    if (row.mode !== RANDOM_MODE.mode) card.append(group);
    card.addEventListener('click', () => { close(); onPick?.(row.mode); });
    grid.append(card);
    if (active) selected = card;
  }
  const footer = document.createElement('div'); footer.className = 'm81350-footer';
  footer.textContent = 'Chọn một bản đồ · "Ngẫu nhiên": mỗi phòng server tự bốc một bản đồ khác';
  body.append(heading, grid, footer);
  shade.append(panel.root);
  shade.addEventListener('click', event => { if (event.target === shade) close(); });
  shade.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } });
  host.append(shade);
  (selected || grid.lastElementChild)?.focus();
  return close;
}

// Room trigger labels are styled before any picker is opened.
if (typeof document !== 'undefined' && document.head) ensureStyle();

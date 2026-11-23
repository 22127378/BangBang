// M46: restored native PvE map-script presentation (offline S1797).
// DialogTemplate iType 4 = speech with portrait (queued like the Flash talk
// box), iType 8 = wave/stage banner, iType 11 = map hint bubble anchored at
// its native world position. iType 3 is a Flash cg*.swf cutscene that HTML5
// cannot play, so it is skipped. Display only: no gameplay state here.
const STYLE_ID = 'm81346-pve-dialog-style';
const CSS = `
.pve-script-layer{position:absolute;inset:0;pointer-events:none;z-index:5;overflow:hidden;font-family:inherit}
.pve-talk{position:absolute;left:3%;right:3%;bottom:4%;display:flex;align-items:flex-end;gap:12px;
  max-width:760px;margin:0 auto;opacity:0;transform:translateY(12px);transition:opacity .25s,transform .25s}
.pve-talk.show{opacity:1;transform:none}
.pve-talk img{width:96px;height:96px;object-fit:contain;flex:0 0 96px;filter:drop-shadow(0 2px 4px #000a)}
.pve-talk img[hidden]{display:none}
.pve-talk p{margin:0;flex:1;min-height:56px;padding:12px 16px;border-radius:10px;font-size:15px;line-height:1.45;
  color:#fff7df;background:linear-gradient(180deg,#1d3348f0,#0d1b29f0);border:1px solid #e3b65c;
  box-shadow:0 4px 18px #000b;white-space:pre-line;text-shadow:0 1px 2px #000}
.pve-banner{position:absolute;left:0;right:0;top:22%;text-align:center;font-size:34px;font-weight:800;letter-spacing:1px;
  color:#ffe27a;text-shadow:0 0 12px #000,0 2px 0 #7a3c00;opacity:0;transition:opacity .3s}
.pve-banner.show{opacity:1}
.pve-hint{position:absolute;transform:translate(-50%,-100%);max-width:220px;padding:6px 10px;border-radius:8px;
  font-size:12px;line-height:1.35;color:#1d1200;background:#ffe9a8f2;border:1px solid #b07a1f;
  box-shadow:0 2px 8px #0008;white-space:pre-line;text-align:center}
.pve-hint::after{content:'';position:absolute;left:50%;bottom:-7px;margin-left:-6px;border:6px solid transparent;
  border-top-color:#ffe9a8f2;border-bottom:0}
.pve-hint.top{left:50%;top:10%;transform:translateX(-50%)}
.pve-hint.top::after{display:none}
@media(max-width:560px){.pve-talk img{width:64px;height:64px;flex-basis:64px}.pve-talk p{font-size:13px}.pve-banner{font-size:24px}}
`;

function ensureStyle() {
  if (typeof document === 'undefined' || document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID; style.textContent = CSS;
  document.head.append(style);
}

const seconds = (value, fallback) => (Number.isFinite(value) && value > 0 ? value : fallback) * 1000;

export class PveDialogLayer {
  constructor(stage) {
    this.stage = stage; this.root = null; this.sceneId = null;
    this.queue = []; this.current = null; this.banners = []; this.banner = null; this.hints = [];
  }

  mount() {
    if (this.root || !this.stage) return;
    ensureStyle();
    this.root = document.createElement('div');
    this.root.className = 'pve-script-layer'; this.root.setAttribute('aria-live', 'polite');
    this.talk = document.createElement('div'); this.talk.className = 'pve-talk';
    this.portrait = document.createElement('img'); this.portrait.alt = ''; this.portrait.hidden = true;
    this.portrait.addEventListener('error', () => { this.portrait.hidden = true; });
    this.talkText = document.createElement('p');
    this.talk.append(this.portrait, this.talkText);
    this.bannerNode = document.createElement('div'); this.bannerNode.className = 'pve-banner';
    this.root.append(this.talk, this.bannerNode);
    this.stage.append(this.root);
  }

  reset() {
    this.queue = []; this.current = null; this.banners = []; this.banner = null;
    for (const hint of this.hints) hint.node.remove();
    this.hints = [];
    if (this.root) { this.talk.classList.remove('show'); this.bannerNode.classList.remove('show'); }
  }

  consume(events, state) {
    if (state?.sceneId !== this.sceneId) { this.reset(); this.sceneId = state?.sceneId ?? null; }
    for (const event of events || []) {
      if (event.kind !== 'pveDialog') continue;
      const p = event.packet || {}, at = event.receivedAt ?? 0;
      const text = String(p.text || '').trim();
      if (!text) continue;
      this.mount();
      const readyAt = at + Math.max(0, Number(p.delay) || 0) * 1000;
      if (p.dialogType === 8) {
        this.banners.push({text, readyAt, duration: seconds(p.duration, 4)});
      } else if (p.dialogType === 11 || p.scriptKind === 11) {
        this.addHint(p, text, at);
      } else if (p.dialogType !== 3) {
        // Speech: about 4s plus reading time, as the native talk box waits.
        const reading = Math.min(9000, 2500 + text.length * 70);
        this.queue.push({text, portrait: p.portrait || '', readyAt,
          duration: Math.max(seconds(p.duration, 0) || 0, reading)});
      }
    }
  }

  addHint(p, text, now) {
    const node = document.createElement('div');
    const anchored = Number(p.x) > 0 && Number(p.y) > 0;
    node.className = 'pve-hint' + (anchored ? '' : ' top');
    node.textContent = text;
    this.root.append(node);
    // Native iTime -1 hints stay while relevant; keep them for a while so
    // they are readable without covering the map for the whole run.
    this.hints.push({node, x: Number(p.x), y: Number(p.y), anchored,
      until: now + seconds(p.duration, 15)});
    while (this.hints.length > 4) this.hints.shift().node.remove();
  }

  tick(now, view, finished = false) {
    if (!this.root) return;
    if (finished && (this.hints.length || this.banners.length || this.banner)) {
      // Closing speech (native last stage) may still play over the result.
      for (const hint of this.hints) hint.node.remove();
      this.hints = []; this.banners = []; this.banner = null; this.bannerNode.classList.remove('show');
    }
    // Speech queue.
    if (this.current && now >= this.current.until) {
      this.current = null; this.talk.classList.remove('show');
    }
    if (!this.current && this.queue.length && now >= this.queue[0].readyAt) {
      const next = this.queue.shift();
      this.current = {...next, until: now + next.duration};
      this.talkText.textContent = next.text;
      if (next.portrait) { this.portrait.src = next.portrait; this.portrait.hidden = false; }
      else { this.portrait.hidden = true; this.portrait.removeAttribute('src'); }
      this.talk.classList.add('show');
    }
    // Banner.
    if (this.banner && now >= this.banner.until) { this.banner = null; this.bannerNode.classList.remove('show'); }
    if (!this.banner && this.banners.length && now >= this.banners[0].readyAt) {
      const next = this.banners.shift();
      this.banner = {...next, until: now + next.duration};
      this.bannerNode.textContent = next.text; this.bannerNode.classList.add('show');
    }
    // World-anchored hints follow the camera.
    this.hints = this.hints.filter(hint => {
      if (now >= hint.until) { hint.node.remove(); return false; }
      if (hint.anchored && view?.screenPoint && view.width > 0 && view.height > 0) {
        const point = view.screenPoint(hint.x, hint.y);
        const visible = point.x >= 0 && point.y >= 0 && point.x <= view.width && point.y <= view.height;
        hint.node.style.visibility = visible ? 'visible' : 'hidden';
        hint.node.style.left = `${point.x / view.width * 100}%`;
        hint.node.style.top = `${point.y / view.height * 100}%`;
      }
      return true;
    });
  }
}

// M49: native BuffTemplate icons that exist in /rez but were never bound to
// m6 buff resources (mostly guild active/passive skill buffs). Display only:
// buff ids, timers and effects are untouched; an existing binding wins.
const loads = new Map();

export function loadM81349BuffIcons(url = './m81349_buff_icons.json', {refresh = false} = {}) {
  if (refresh) loads.delete(url);
  if (!loads.has(url)) loads.set(url, fetch(url, {cache: 'no-store'})
    .then(response => response.ok ? response.json() : null)
    .then(value => value?.schemaVersion === 1 && value.icons && typeof value.icons === 'object' ? value : null)
    .catch(() => null));
  return loads.get(url);
}

export async function mergeM81349BuffIcons(catalog, options) {
  const data = await loadM81349BuffIcons(undefined, options);
  if (!data || !catalog?.buffs) return 0;
  let merged = 0;
  for (const [id, asset] of Object.entries(data.icons)) {
    const buff = catalog.buffs[id];
    if (!buff || buff.resources?.szBuffIcon || typeof asset?.url !== 'string' || !asset.url.startsWith('/rez/')) continue;
    try { buff.resources = {...(buff.resources || {}), szBuffIcon: {...asset}}; merged += 1; } catch {}
  }
  return merged;
}

/** Native BuffProxy only lists buffs that have a real icon. */
export function hasNativeBuffIcon(template) {
  const asset = template?.resources?.szBuffIcon, url = String(asset?.url || '');
  if (!url || url.endsWith('.swf') || /offline_empty_buff\.png$/i.test(String(asset?.logical || url))) return false;
  return !(Number(asset?.width) <= 1 && Number(asset?.height) <= 1);
}

"""Restored native PvE presentation scripts.

The imported maps keep every native script record, but the chapter
controllers only executed the gameplay kinds (3/4/5/7). This module restores
the presentation kinds, without touching spawns, rewards or geometry:

  kind 1  show a guide arrow map object (maptips3_*)
  kind 2  hide that guide arrow
  kind 6  play a DialogTemplate row (speech, wave banner, cutscene)
  kind 11 show a DialogTemplate hint bubble at its native map position

Dialogs are sent to the HTML5 client as the offline-only S1797 message. Text
comes from the reviewed Vietnamese file pve_dialog_vi.txt; unknown rows fall
back to the native Chinese text instead of being dropped.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

from combat_protocol import scene

MSG_DIALOG = 1797
PRESENTATION_KINDS = frozenset((1, 2, 6, 11))
ROOT = Path(__file__).resolve().parent.parent
VI_PATH = Path(__file__).with_name('pve_dialog_vi.txt')
TIPS_DIR = 'zh_CN/gui_summer/controls/tips/'


@lru_cache(maxsize=1)
def _vietnamese() -> dict[int, str]:
    rows = {}
    try:
        for line in VI_PATH.read_text(encoding='utf-8').splitlines():
            if line[:1].isdigit() and '|' in line:
                ident, text = line.split('|', 1)
                rows[int(ident)] = text.strip()
    except OSError:
        pass
    return rows


@lru_cache(maxsize=1)
def _dialogs() -> dict[int, dict[str, str]]:
    path = ROOT / 'data' / 'xmlpack' / 'DialogTemplate_table.xml'
    rows = {}
    try:
        for entry in ET.parse(path).iter('entry'):
            row = {child.tag: (child.text or '') for child in entry}
            if row.get('nId', '').lstrip('-').isdigit():
                rows[int(row['nId'])] = row
    except (OSError, ET.ParseError):
        pass
    return rows


@lru_cache(maxsize=1)
def _resources() -> dict[str, str]:
    path = ROOT / 'data' / 'fileList_unpacked.xml'
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return {}
    return dict(re.findall(r'<key>([^<]+)</key>\s*<value>([^<]+)</value>', text))


def resource_url(name: str) -> str:
    """Native tips artwork -> served /rez URL; only existing PNG files."""
    if not name or not name.lower().endswith('.png'):
        return ''
    value = _resources().get(TIPS_DIR + name)
    if not value or not (ROOT / 'www' / 'rez' / value).is_file():
        return ''
    return '/rez/' + value


def _int(value, default=0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _wave_number(image: str) -> int:
    match = re.search(r'tip_wave(\d+)', image or '')
    return int(match.group(1)) if match else 0


def dialog_packet(arena, dialog_id: int, kind: int):
    row = _dialogs().get(dialog_id)
    if row is None:
        return None
    dtype = _int(row.get('iType'))
    text = _vietnamese().get(dialog_id) or row.get('szContent', '')
    image = row.get('szImage', '')
    if dtype == 8:
        wave = _wave_number(image)
        if wave:
            text = f'Đợt {wave}'
        else:
            # Rows 33xx carry no artwork: the native stage-opening banner.
            from pve_catalog import NAMES
            text = NAMES.get(arena.geometry.id, '') or 'Bắt đầu nhiệm vụ'
    elif dtype == 3:
        # Native Flash cutscene (cg*.swf). HTML5 cannot play SWF; the client
        # shows a short skippable caption instead of silently dropping it.
        text = text or 'Đoạn phim cốt truyện'
    if not text:
        return None
    text = text.replace('#n#', '\n')
    portrait = resource_url(image) if dtype == 4 else ''
    background = resource_url(row.get('szBgImage', '')) if dtype == 4 else ''
    duration = _int(row.get('iTime'), -1)
    delay = _int(row.get('nDelayTime'), 0)
    x, y = (_int(row.get('iReuseA')), _int(row.get('iReuseB'))) if kind == 11 else (0, 0)
    body = struct.pack('<IIBBhHhh', arena.scene_id, dialog_id, kind, dtype,
                       max(-1, min(duration, 32767)), max(0, min(delay, 65535)),
                       max(-32768, min(x, 32767)), max(-32768, min(y, 32767)))
    for value in (text, portrait, background):
        data = value.encode('utf-8')[:4000]
        body += struct.pack('<H', len(data)) + data
    return MSG_DIALOG, body


def _arrow(arena, instance: int):
    return next((n for n in arena.geometry.data.get('npcs', ()) if n.get('instance') == instance), None)


def _script_lists(data):
    for group in ('pve_zones', 'pve_waves'):
        for row in data.get(group, ()):
            yield row.get('scripts') or ()
    for row in data.get('npcs', ()):
        yield row.get('pve_scripts') or ()


def _gated(arena) -> frozenset:
    """Decorations a native kind-1 script reveals: hidden until that script."""
    cached = getattr(arena.geometry, '_pve_gated_arrows', None)
    if cached is None:
        cached = frozenset(int(s[1]) for script in _script_lists(arena.geometry.data)
                           for s in script if s and int(s[0]) == 1)
        try:
            arena.geometry._pve_gated_arrows = cached
        except AttributeError:
            pass
    return cached


def visible(arena, instance: int) -> bool:
    """Current visibility of a script-controlled decoration (default: native)."""
    pve = (arena.pk or {}).get('pve') or {}
    override = (pve.get('pve_arrows') or {}).get(str(instance))
    if override is not None:
        return bool(override)
    return instance not in _gated(arena)


def _arrow_packets(arena, kind: int, instance: int):
    ident = (3 << 26) | instance
    if ident in arena.actors:
        return []  # A real gameplay object; presentation never touches it.
    definition = _arrow(arena, instance)
    if definition is None or definition.get('hp', 0) > 0:
        return []
    want = kind == 1
    if visible(arena, instance) == want:
        return []
    arena.pk.setdefault('pve', {}).setdefault('pve_arrows', {})[str(instance)] = want
    if want:
        body = struct.pack('<IIIhhiBiIiH', arena.scene_id, ident, definition['template'],
                           round(definition['x']), round(definition['y']), definition['hp'],
                           definition['camp'], definition['hp'], 0, 0, 0)
        return [(1556, body)]
    return [scene(removed=(struct.pack('<I', ident),))]


def _removed_object_lines(arena, instance: int, now) -> list:
    actor = arena.actors.get((3 << 26) | instance)
    if actor is None or not actor.alive:
        return []
    definition = _arrow(arena, instance)
    lines = [s for s in (definition or {}).get('pve_scripts') or ()
             if s and int(s[0]) in PRESENTATION_KINDS]
    return run(arena, lines, now) if lines else []


def run(arena, script, now) -> list:
    """Presentation-only kinds of one native script list. Never raises."""
    packets = []
    if not script or arena.pk is None or arena.pk.get('finished'):
        return packets
    for record in script:
        try:
            kind, arg = int(record[0]), int(record[1])
        except (TypeError, ValueError, IndexError):
            continue
        if kind == 4:
            # Script dismantling (rescued cage, opened gate...) is that
            # object's native destruction: play its presentation lines too.
            packets += _removed_object_lines(arena, arg, now)
            continue
        if kind not in PRESENTATION_KINDS:
            continue
        try:
            if kind in (1, 2):
                packets += _arrow_packets(arena, kind, arg)
            else:
                packet = dialog_packet(arena, arg, kind)
                if packet:
                    packets.append(packet)
        except Exception:  # Presentation must never break a PvE run.
            continue
    return packets


def wave_lines(arena, wave: int, now) -> list:
    """Chapters 7-9 keep presentation-only wave scripts; play one stage."""
    packets = []
    for row in arena.geometry.data.get('pve_waves', ()):
        if row.get('fields') == wave:
            packets += run(arena, [s for s in row.get('scripts') or () if s and int(s[0]) in PRESENTATION_KINDS], now)
    return packets


def ending_lines(arena, now) -> list:
    """Native closing stage (wave >= 2) of chapters 7-9, sent before the result."""
    from pve_catalog import CHAPTER7, CHAPTER8, CHAPTER9
    if arena.geometry.id not in CHAPTER7 + CHAPTER8 + CHAPTER9 or arena.pk.get('finished'):
        return []
    waves = sorted({row['fields'] for row in arena.geometry.data.get('pve_waves', ())
                    if isinstance(row.get('fields'), int) and row['fields'] >= 2})
    packets = []
    for wave in waves:
        packets += wave_lines(arena, wave, now)
    return packets

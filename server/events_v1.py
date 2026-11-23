"""events-v1: offline implementation of the ActivityTemplate "fixed" events.

The original game server logic for these activities is not part of this
package, only their data tables. Each event below is an explicit offline rule
built from that data (see RULES in the docstring of every builder). Rewards,
debits and the per-profile event state are committed in ONE transaction with
an idempotency receipt; nothing is granted twice for a retried request.

Transport: C60012 JSON request -> native wallet/bag packets + S60013 JSON reply.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, date, timedelta
from functools import lru_cache
from pathlib import Path
import json
import random
import re
import struct
import time
import xml.etree.ElementTree as ET

import cosmetic_shop
import inventory
import mail_rewards
import storage
from mail_rewards import RewardError

REQUEST, REPLY, VERSION = 60012, 60013, 1
SETTING = 'events_v1'
ROOT = Path(__file__).resolve().parent.parent
XML = ROOT / 'data' / 'xmlpack'
COIN = {1: 'cash', 2: 'golden', 3: 'gift'}            # native COIN_* -> wallet key
CURRENCY_INDEX = {key: index for key, (index, _) in mail_rewards.CURRENCIES.items()}
TICKET_PRICE = 20                                     # Xu per extra roulette ticket (offline rule)
_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
_KEY = re.compile(r'^[A-Za-z0-9_.:-]{0,64}$')


# ---------------------------------------------------------------- data
def _rows(name):
    try:
        return [{c.tag: (c.text or '') for c in e} for e in ET.parse(XML / f'{name}.xml').iter('entry')]
    except (OSError, ET.ParseError):
        return []


def _n(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def _items():
    return {_n(r.get('nItemId')): r for r in _rows('ItemTemplate_table')}


@lru_cache(maxsize=1)
def _presents():
    out = {}
    for r in _rows('ItemPresentTemplate_table'):
        out.setdefault(_n(r.get('nPresentId')), []).append(r)
    return out


@lru_cache(maxsize=1)
def _gift_rows():
    out = {}
    for r in _rows('CharGiftTemplate_table'):
        out.setdefault(_n(r.get('nGiftType')), []).append(r)
    for rows in out.values():
        rows.sort(key=lambda r: (_n(r.get('nLevel')), _n(r.get('nCheckVal'))))
    return out


def _gift_rewards(row):
    rewards = []
    for i in range(1, 6):
        ident, count = _n(row.get(f'nItemId{i}')), _n(row.get(f'nItemId{i}Count'))
        if ident > 0 and count > 0:
            rewards.append(dict(kind='item', id=ident, quantity=count))
    return rewards


@lru_cache(maxsize=1)
def _roulettes():
    out = {}
    for r in _rows('RouletteTemplate_table'):
        out.setdefault(_n(r.get('nType')), []).append(dict(
            id=_n(r.get('nID')), item=_n(r.get('nItemID')), quantity=max(1, _n(r.get('iCount'), 1)),
            weight=max(0, _n(r.get('nDropRate'))), ticket=_n(r.get('nNeedItemId')), lucky=_n(r.get('nShowLucky'))))
    return out


@lru_cache(maxsize=1)
def _converts():
    out = []
    for r in _rows('ItemConvertTemplate_table'):
        if _n(r.get('nType')) != 32 or _n(r.get('nNewItemId')) <= 0:
            continue
        cost = [(_n(r.get(f'nItemId{i}')), _n(r.get(f'iCount{i}'))) for i in range(1, 6)]
        cost = [(i, c) for i, c in cost if i > 0 and c > 0]
        if cost:
            out.append(dict(key=f'cv{_n(r.get("nId"))}', cost=cost, item=_n(r.get('nNewItemId')),
                            quantity=max(1, _n(r.get('nNewItemCount'), 1))))
    return out


@lru_cache(maxsize=1)
def _fund():
    return sorted(({'day': _n(r.get('nDay')), 'money': _n(r.get('nMoney'))}
                   for r in _rows('FundTemplate_table') if not r.get('nType')), key=lambda r: r['day'])


@lru_cache(maxsize=1)
def _mystical():
    return [r for r in _rows('MysticalShopTemplate_table') if _n(r.get('nTankId')) > 0]


@lru_cache(maxsize=1)
def _campfire_marks():
    marks = []
    for r in _rows('QuestTemplate_table'):
        if _n(r.get('nCheckType')) == 139 and _n(r.get('nCheckCount')) > 0:
            rewards = [dict(kind='item', id=_n(r.get(f'nItemId{i}')), quantity=_n(r.get(f'nItemCount{i}')))
                       for i in range(1, 5) if _n(r.get(f'nItemId{i}')) > 0 and _n(r.get(f'nItemCount{i}')) > 0]
            marks.append(dict(key=f'q{_n(r.get("nQuestId"))}', need=_n(r.get('nCheckCount')),
                              name=r.get('szName') or 'Mốc Lửa Trại', rewards=rewards))
    return sorted(marks, key=lambda m: m['need'])


# ---------------------------------------------------------------- rewards
def _expand(rewards, depth=0):
    """Open currency packs / bundles (ItemPresentTemplate) and tank cards."""
    out = []
    for reward in rewards:
        if reward['kind'] != 'item':
            out.append(dict(reward)); continue
        row = _items().get(reward['id'], {})
        pack = _presents().get(reward['id'])
        kind = _n(row.get('nType'))
        if pack and depth < 3 and kind in (20, 51):
            for part in pack:
                count = _n(part.get('iCount')) * reward['quantity']
                if count <= 0:
                    continue
                if _n(part.get('nGiveType')) == 2 and _n(part.get('nReuseA')) in COIN:
                    out.append(dict(kind='currency', id=COIN[_n(part.get('nReuseA'))], quantity=count))
                elif _n(part.get('nGiveType')) == 1 and _n(part.get('nReuseA')) > 0:
                    out += _expand([dict(kind='item', id=_n(part.get('nReuseA')), quantity=count)], depth + 1)
        elif kind == 46 and _n(row.get('iReuseA')) >= 10000000:
            out.append(dict(kind='tank', id=_n(row.get('iReuseA')), quantity=1))
        else:
            out.append(dict(reward))
    merged = {}
    for reward in out:
        key = (reward['kind'], reward['id'])
        merged[key] = merged.get(key, 0) + reward['quantity']
    return [dict(kind=k, id=i, quantity=q) for (k, i), q in merged.items()]


def _base(db):
    """Same shape as mail_rewards.plan for debits / generic-only grants."""
    containers = inventory.load(db)
    wallet = cosmetic_shop.snapshot(db)
    return dict(rewards=[], before=deepcopy(containers), containers=containers, wallet=wallet,
                new_tanks=[], garage=[])


def _generic(item_id, quantity):
    """Plain stackable material/grocery item that the bag can hold."""
    row = _items().get(item_id)
    if not row or _n(row.get('nAutoUse')):
        return None
    cont, maximum = _n(row.get('nContType')), _n(row.get('iStackMax'))
    if cont not in (2, 3) or not 1 <= maximum <= mail_rewards.MAX_INT:
        return None
    return dict(key=f'item:{item_id}', kind='item', id=item_id, quantity=quantity, container=cont,
                stack_max=maximum, unique=False, level=0, name=row.get('szName') or f'Vật phẩm {item_id}')


def _plan(db, rewards, available):
    """mail_rewards plan for catalog rewards + direct bag grant for generic items."""
    rewards = _expand(rewards)
    approved, generic, skipped = [], [], []
    for reward in rewards:
        key = f"{reward['kind']}:{reward['id']}"
        if key in available:
            if reward['kind'] == 'tank' and reward['quantity'] > 1:
                reward = dict(reward, quantity=1)
            approved.append(reward)
        elif reward['kind'] == 'item' and (desc := _generic(reward['id'], reward['quantity'])):
            generic.append(desc)
        else:
            skipped.append(reward)
    if len(approved) > mail_rewards.MAX_ROWS:
        raise RewardError('too_many_rewards', 'Phần thưởng quá nhiều dòng; hãy báo lỗi dữ liệu sự kiện.')
    value = mail_rewards.plan(db, storage.profile_id(), approved, available) if approved else _base(db)
    capacities = dict(mail_rewards.CAPACITIES)
    capacities[2] = inventory.grocery_capacity(db)
    for desc in generic:
        mail_rewards._grant_item(value['containers'], desc, capacities)
    value['granted'] = approved + [dict(kind='item', id=d['id'], quantity=d['quantity']) for d in generic]
    value['skipped'] = skipped
    return value


def _item_name(item_id):
    """Vietnamese display name (M31 locale), falling back to the template text."""
    source = (_items().get(item_id) or {}).get('szName') or f'Vật phẩm {item_id}'
    try:
        from display_locale import _locale
        return _locale().get('translations', {}).get(source, source)
    except Exception:
        return source


def _count(containers, template):
    return sum(i.get('count', 0) for c in ('2', '3', '5') for i in containers.get(c, [])
               if i.get('template_id') == template and not (i.get('ext_flag', 0) & 2) and not i.get('life_time'))


def _take(containers, template, count):
    if _count(containers, template) < count:
        name = (_items().get(template) or {}).get('szName') or f'vật phẩm {template}'
        raise RewardError('not_enough_items', f'Không đủ {name} (cần {count}).')
    for cont in ('2', '3', '5'):
        bag = containers.get(cont, [])
        for item in sorted(list(bag), key=lambda i: i.get('slot_no', 0)):
            if count <= 0:
                break
            if item.get('template_id') != template or (item.get('ext_flag', 0) & 2) or item.get('life_time'):
                continue
            used = min(count, item['count'])
            item['count'] -= used
            count -= used
            if item['count'] <= 0:
                bag.remove(item)


def _pay(value, currency, amount):
    index = CURRENCY_INDEX[currency]
    if value['wallet']['currency'][index] < amount:
        raise RewardError('insufficient_funds', f'Không đủ {mail_rewards.CURRENCIES[currency][1]} (cần {amount}).')
    value['wallet']['currency'][index] -= amount


# ---------------------------------------------------------------- state
def _today():
    return date.today().isoformat()


def _load(db):
    state = cosmetic_shop._get(db, SETTING, {})
    state.setdefault('receipts', {})
    return state


def _daily(state, key):
    """Per-day sub-state that resets at local midnight."""
    box = state.setdefault(key, {})
    if box.get('date') != _today():
        box.clear(); box['date'] = _today()
    return box


def _touch_online(state, now):
    box = _daily(state, 'online')
    last = box.get('last', 0)
    if last and 0 < now - last <= 300:
        box['seconds'] = box.get('seconds', 0) + int(now - last)
    box['last'] = int(now)
    return box.get('seconds', 0)


# ---------------------------------------------------------------- events
def _row(key, title, rewards=(), *, sub='', op='', label='Nhận', enabled=False, state='locked', cost=None):
    return dict(key=key, title=title, sub=sub, rewards=list(rewards), cost=cost or [],
                button=dict(op=op, label=label, enabled=bool(enabled and op)), state=state)


def _ev_growth(st, ctx):
    """Quà Trưởng Thành: CharGift type 1 + 5, one claim per level milestone."""
    claimed, level = set(st.get('growth', [])), ctx['level']
    rows = []
    for gtype, label in ((1, 'Quà cấp'), (5, 'Quà cấp bổ sung')):
        for r in _gift_rows().get(gtype, []):
            need, key = _n(r.get('nLevel')), f'g{gtype}-{_n(r.get("nLevel"))}'
            done = key in claimed
            rows.append(_row(key, f'{label} {need}', _gift_rewards(r), sub=f'Nhân vật đạt cấp {need}',
                             op='claim', enabled=not done and level >= need,
                             state='claimed' if done else 'claimable' if level >= need else 'locked'))
    return dict(sections=[dict(title=f'Cấp hiện tại: {level}', rows=rows)])


def _ev_return(st, ctx):
    """Tri Ân Người Chơi Quay Lại: type 3 welcome pack + type 2 login days 1..8."""
    box = st.setdefault('return', {})
    days = box.setdefault('days', [])
    rows = []
    for r in _gift_rows().get(3, []):
        done = box.get('pack')
        rows.append(_row('pack', 'Quà chào mừng trở lại', _gift_rewards(r), op='claim', enabled=not done,
                         state='claimed' if done else 'claimable'))
    today_done = box.get('last_day') == _today()
    for r in _gift_rows().get(2, []):
        n = _n(r.get('nLevel')); key = f'd{n}'
        done = key in days
        ready = not done and len(days) + 1 == n and not today_done
        rows.append(_row(key, f'Đăng nhập ngày {n}', _gift_rewards(r), sub='Mỗi ngày nhận 1 mốc',
                         op='claim', enabled=ready, state='claimed' if done else 'claimable' if ready else 'locked'))
    return dict(sections=[dict(title='Chào mừng bạn quay lại chiến trường!', rows=rows)])


PEAK_WINDOWS = ((12, 14, 'Trưa 12:00–14:00'), (19, 22, 'Tối 19:00–22:00'))


def _ev_peak(st, ctx):
    """Online Cao Điểm: one gift per peak window per day (CharGift type 6, cycling by weekday)."""
    box = _daily(st, 'peak')
    gifts = _gift_rows().get(6, [])
    hour = datetime.now().hour
    rows = []
    for start, end, label in PEAK_WINDOWS:
        key = f'w{start}'
        reward = _gift_rewards(gifts[datetime.now().weekday() % len(gifts)]) if gifts else []
        active, done = start <= hour < end, key in box
        rows.append(_row(key, label, reward, sub='Online trong khung giờ để nhận', op='claim',
                         enabled=active and not done, state='claimed' if done else 'claimable' if active else 'locked'))
    return dict(sections=[dict(title='Quà online giờ cao điểm', rows=rows)])


def _ev_online(st, ctx):
    """Thưởng Online Toàn Server: CharGift type 8, nLevel = minutes online today."""
    box = _daily(st, 'online')
    minutes = box.get('seconds', 0) // 60
    rows = []
    for r in _gift_rows().get(8, []):
        need = _n(r.get('nLevel')); key = f'm{need}'
        done = key in box.get('claimed', [])
        rows.append(_row(key, f'Online {need} phút', _gift_rewards(r), op='claim',
                         enabled=not done and minutes >= need,
                         state='claimed' if done else 'claimable' if minutes >= need else 'locked'))
    return dict(sections=[dict(title=f'Hôm nay đã online {minutes} phút (cập nhật khi mở sảnh)', rows=rows)])


GROUP_PRICE, GROUP_SHARES = 20, 10


def _ev_group(st, ctx):
    """Mua Chung: daily featured pack (CharGift type 7); 10 shares x 20 Xu khóa."""
    box = _daily(st, 'group')
    prize = _gift_rewards(_gift_rows().get(7, [{}])[0]) if _gift_rows().get(7) else []
    shares, done = box.get('shares', 0), box.get('done')
    rows = [_row('share', f'Mua 1 phần ({shares}/{GROUP_SHARES})', [], sub=f'{GROUP_PRICE} Xu khóa mỗi phần',
                 op='buy_share', label='Mua phần', enabled=not done and shares < GROUP_SHARES,
                 state='claimed' if done else 'claimable', cost=[dict(kind='currency', id='gift', quantity=GROUP_PRICE)]),
            _row('prize', 'Nhận quà mua chung', prize, sub=f'Đủ {GROUP_SHARES} phần trong ngày', op='claim',
                 enabled=not done and shares >= GROUP_SHARES,
                 state='claimed' if done else 'claimable' if shares >= GROUP_SHARES else 'locked')]
    return dict(sections=[dict(title='Góp đủ phần để nhận gói quà hôm nay', rows=rows)])


FUND_PRICE = 100


def _ev_fund(st, ctx):
    """Quỹ Đầu Tư: buy for 100 Xu, then claim day N on the N-th calendar day."""
    box = st.setdefault('fund', {})
    bought = box.get('bought')
    rows = [_row('buy', 'Mua Quỹ Đầu Tư', [], sub=f'Giá {FUND_PRICE} Xu, nhận lại Xu theo ngày', op='buy_fund',
                 label='Mua quỹ', enabled=not bought, state='claimed' if bought else 'claimable',
                 cost=[dict(kind='currency', id='cash', quantity=FUND_PRICE)])]
    elapsed = (date.today() - date.fromisoformat(bought)).days + 1 if bought else 0
    claimed = set(box.get('claimed', []))
    for r in _fund():
        key = f'd{r["day"]}'; done = key in claimed
        ok = bool(bought) and not done and r['day'] <= elapsed
        rows.append(_row(key, f'Ngày {r["day"]}', [dict(kind='currency', id='cash', quantity=r['money'])],
                         op='claim', enabled=ok, state='claimed' if done else 'claimable' if ok else 'locked'))
    return dict(sections=[dict(title='Đầu tư một lần, nhận Xu mỗi ngày', rows=rows)])


def _mystical_today():
    rows = _mystical()
    rng = random.Random(_today())
    return rng.sample(rows, min(4, len(rows))) if rows else []


def _ev_mystical(st, ctx):
    """Chợ Thần Bí: 4 tanks/day (seeded by date), discounted cards/gifts/skins, once per offer."""
    box = _daily(st, 'mystical')
    rows = []
    for r in _mystical_today():
        tank = _n(r.get('nTankId'))
        for field, price_field, base_field, label in (('nTankCardId', 'nTankDiscountPrice', 'nTankOrginalPrice', 'Thẻ tank'),
                                                       ('nGiftId', 'nGiftDiscountPrice', 'nGiftOrginalPrice', 'Gói quà'),
                                                       ('nSkin2SId', 'nSkin2SDiscountPrice', 'nSkin2SOrginalPrice', 'Skin S'),
                                                       ('nSkin3SId', 'nSkin3SDiscountPrice', 'nSkin3SOrginalPrice', 'Skin SS')):
            item, price = _n(r.get(field)), _n(r.get(price_field))
            if item <= 0 or price <= 0:
                continue
            key = f'{tank}-{field}'; done = key in box.get('bought', [])
            owned = any(x['kind'] == 'tank' and x['id'] in ctx['owned'] for x in _expand([dict(kind='item', id=item, quantity=1)]))
            rows.append(_row(key, f'{label}: {_item_name(item)}', [dict(kind='item', id=item, quantity=1)],
                             sub='Đã sở hữu tank này' if owned else f'Giá gốc {_n(r.get(base_field))} → {price} Xu',
                             op='buy', label='Đã có' if owned else 'Mua',
                             enabled=not done and not owned, state='claimed' if done else 'owned' if owned else 'claimable',
                             cost=[dict(kind='currency', id='cash', quantity=price)]))
    return dict(sections=[dict(title='Hàng giảm giá đổi mỗi ngày', rows=rows)])


def _roulette_view(st, rtype, label):
    cells = [c for c in _roulettes().get(rtype, []) if c['weight'] > 0]
    box = st.setdefault(f'r{rtype}', {})
    daily = _daily(st, f'r{rtype}_daily')
    return dict(cells=[dict(id=c['id'], kind='item', item=c['item'], quantity=c['quantity'], lucky=bool(c['lucky']))
                       for c in cells],
                tickets=box.get('tickets', 0), ticketName=label, ticketPrice=TICKET_PRICE,
                freeReady=not daily.get('free'), last=box.get('last'))


def _ev_luck(st, ctx):
    """Vòng Quay May Mắn: RouletteTemplate type 14; 1 free ticket per day (quest 27010)."""
    return dict(roulette=_roulette_view(st, 14, 'Xúc Xắc Vòng Quay'), sections=[])


def _ev_slot(st, ctx):
    """VN Luck Slot: RouletteTemplate type 13 + ItemConvert type 32 exchange list."""
    rows = []
    for c in _converts():
        have = min(_count(ctx['containers'], i) // n for i, n in c['cost']) if c['cost'] else 0
        rows.append(_row(c['key'], _item_name(c['item']) + (f" x{c['quantity']}" if c['quantity'] > 1 else ''),
                         [dict(kind='item', id=c['item'], quantity=c['quantity'])],
                         sub=f'Có thể đổi {have} lần', op='exchange', label='Đổi', enabled=have > 0,
                         state='claimable' if have > 0 else 'locked',
                         cost=[dict(kind='item', id=i, quantity=n) for i, n in c['cost']]))
    return dict(roulette=_roulette_view(st, 13, 'Vé May Mắn'), sections=[dict(title='Đổi thưởng', rows=rows)])


WOOD_DAILY = 5


def _ev_campfire(st, ctx):
    """Tiệc Lửa Trại: 5 Củi/day; each Củi adds 1 fire; milestones from quests nCheckType 139."""
    box = st.setdefault('campfire', {})
    daily = _daily(st, 'campfire_daily')
    fires, wood = box.get('fires', 0), box.get('wood', 0)
    rows = [_row('wood', f'Nhận {WOOD_DAILY} Củi Lửa Trại hôm nay', [], op='claim_wood', label='Nhận củi',
                 enabled=not daily.get('wood'), state='claimed' if daily.get('wood') else 'claimable'),
            _row('fire', f'Thêm củi vào lửa (đang có {wood} củi)', [], sub=f'Đã tiếp lửa {fires} lần',
                 op='add_wood', label='Tiếp lửa', enabled=wood > 0, state='claimable' if wood > 0 else 'locked')]
    claimed = set(box.get('claimed', []))
    for m in _campfire_marks():
        done = m['key'] in claimed
        rows.append(_row(m['key'], f'Mốc {m["need"]} lần tiếp lửa', m['rewards'], op='claim',
                         enabled=not done and fires >= m['need'],
                         state='claimed' if done else 'claimable' if fires >= m['need'] else 'locked'))
    return dict(sections=[dict(title='Cùng tiếp lửa để mở rương', rows=rows)])


EVENTS = (
    (351, 'Vòng Quay May Mắn', _ev_luck), (350, 'VN Luck Slot', _ev_slot), (309, 'Chợ Thần Bí', _ev_mystical),
    (990040, 'Tiệc Lửa Trại', _ev_campfire), (99124, 'Quà Trưởng Thành', _ev_growth),
    (99036, 'Quỹ Đầu Tư', _ev_fund), (99042, 'Thưởng Online', _ev_online), (99016, 'Online Cao Điểm', _ev_peak),
    (99035, 'Mua Chung', _ev_group), (99007, 'Tri Ân Quay Lại', _ev_return),
)
EVENT_BY_ID = {ident: (name, fn) for ident, name, fn in EVENTS}


# ---------------------------------------------------------------- periodic (read-only)
# The scheduled ActivityTemplate competitions (same family as Kẻ Hủy Diệt).
# Shown for inspection with their original schedule/rewards; the offline
# server does not run these competition modes, so they expose no actions.
PERIODIC = (
    ('heat', (4, 6, 7), 'Nhiệt Huyết Kích Chiến',
     'Tham gia Nhiệt Huyết Kích Chiến để nhận gấp đôi nguyên liệu, thêm nhiều đá quý và nguyên liệu '
     'thông dụng, còn có cơ hội nhận quà thần bí!'),
    ('fun', (3, 5), 'Giải Vui Vẻ Toàn Dân',
     'Vào đấu trường Giải Vui Vẻ để giành phần thưởng hậu hĩnh. Thứ hạng càng cao, thưởng càng nhiều!'),
    ('league', (2,), 'Siêu Liên Đấu',
     'Muốn đứng trên đỉnh cao, bạn phải đối đầu với mọi cường địch. Chỉ chiến đội mạnh nhất mới vượt '
     'qua tất cả để trở thành nhà vô địch Siêu Liên Đấu!'),
    ('team', (1,), 'Xếp Hạng Chiến Đội',
     'Mỗi chiến đội có thể khiêu chiến các chiến đội xếp trên mình tối đa 10 hạng. Thắng thì hai bên '
     'đổi thứ hạng cho nhau; thua thì thứ hạng giữ nguyên.'),
    ('fire', (401, 402), 'Toàn Dân Hỏa Lực', 'Vào đấu trường Hỏa Lực để giành phần thưởng hậu hĩnh!'),
    ('ball', (403, 404), 'Đấu Fireball', 'Vào đấu trường Fireball để giành phần thưởng hậu hĩnh!'),
    ('ladder', (39,), 'Đấu Thiên Thang', 'Đấu xếp hạng thiên thang (dữ liệu gốc đang đặt ẩn).'),
)
PERIODIC_BASE = 800000                      # view ids; never accepted by decode_request
_WEEKDAY = ('CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7')   # native nDayWeek bit 0 = Sunday


@lru_cache(maxsize=1)
def _activities():
    return {_n(r.get('nId')): r for r in _rows('ActivityTemplate_table')}


def _slot(row):
    """(weekday-bitmask, start-minute, duration) from a native ActivityTemplate row."""
    days = _n(row.get('nDayWeek')) & 127 or 127
    kind, _, clock = (row.get('szStartTime') or 'hour,00:00').partition(',')
    if kind == 'hour':
        hours = _n(row.get('nHour'))
        hour = next((h for h in range(24) if hours >> h & 1), 0)
    else:
        hour = _n(clock.split(':')[0])
    return days, hour * 60, max(1, _n(row.get('nDuration'), 60))


def _days_label(days):
    if days == 127:
        return 'Mỗi ngày'
    return ', '.join(_WEEKDAY[(i + 1) % 7] for i in range(7) if days >> ((i + 1) % 7) & 1)


def _ev_periodic(ids, now):
    rows, sections, live, level, drops = _activities(), [], False, 0, []
    weekday = (now.weekday() + 1) % 7                 # Python Monday=0 -> native Sunday=0
    minute = now.hour * 60 + now.minute
    slots = []
    for ident in ids:
        row = rows.get(ident)
        if not row:
            continue
        level = max(level, _n(row.get('nLevel'), 1))
        for item in (row.get('szDropItems') or '').split('$'):
            if _n(item) and _n(item) not in drops:
                drops.append(_n(item))
        days, start, duration = _slot(row)
        end = start + duration
        today = bool(days >> weekday & 1)
        if today and start <= minute < end:
            state, label, sub = 'claimable', 'Đang mở', f'Còn {end - minute} phút'
            live = True
        elif today and minute < start:
            state, label, sub = 'locked', 'Sắp mở', f'Hôm nay, còn {start - minute} phút nữa'
        elif today:
            state, label, sub = 'claimed', 'Đã kết thúc', 'Hôm nay đã kết thúc'
        else:
            state, label, sub = 'locked', 'Không mở', 'Hôm nay không có lịch'
        e = min(end, 24 * 60)
        title = f'{_days_label(days)} · {start // 60:02d}:{start % 60:02d}–{e // 60:02d}:{e % 60:02d}'
        slots.append((start, _row(f'slot{ident}', title, sub=sub, label=label, state=state)))
    sections.append(dict(title='Lịch diễn ra (theo giờ máy)', rows=[r for _, r in sorted(slots, key=lambda x: x[0])]))
    sections.append(dict(title='Phần thưởng tham gia', rows=[_row(
        'rewards', 'Quà có thể nhận khi tham gia' if drops else 'Dữ liệu gốc không ghi phần thưởng', [dict(kind='item', id=i, quantity=1) for i in drops],
        sub=f'Yêu cầu cấp {level} trở lên', label='Chưa hỗ trợ', state='locked')]))
    return dict(sections=sections, live=live, icons=drops)


def _periodic_views():
    now = datetime.now()
    out = []
    for index, (slug, ids, name, desc) in enumerate(PERIODIC):
        view = _ev_periodic(ids, now)
        out.append(dict(id=PERIODIC_BASE + index, slug=slug, name=name, group='periodic', badge=0,
                        desc=desc, note='Bản offline chưa có chế độ thi đấu này; chỉ hiển thị lịch và phần thưởng gốc.',
                        **view))
    return out


def _views(st, ctx):
    out = []
    for ident, name, fn in EVENTS:
        view = fn(st, ctx)
        badge = sum(1 for s in view.get('sections', []) for r in s['rows'] if r['button']['enabled'] and r['button']['op'] == 'claim')
        roulette = view.get('roulette')
        if roulette and (roulette['freeReady'] or roulette['tickets'] > 0):
            badge += 1
        out.append(dict(id=ident, name=name, badge=badge, group='fixed', **view))
    return out + _periodic_views()


# ---------------------------------------------------------------- actions
def _find_row(view, key):
    for section in view.get('sections', []):
        for row in section['rows']:
            if row['key'] == key:
                return row
    raise RewardError('row_unknown', 'Mục này không còn trong sự kiện; hãy tải lại.')


def _act(db, st, ctx, event, op, key, available):
    """Returns (value-or-None, message, granted)."""
    name, fn = EVENT_BY_ID[event]
    view = fn(st, ctx)
    if op in ('spin', 'free_ticket', 'buy_ticket'):
        rtype = 14 if event == 351 else 13
        box, daily = st.setdefault(f'r{rtype}', {}), _daily(st, f'r{rtype}_daily')
        if op == 'free_ticket':
            if daily.get('free'):
                raise RewardError('already_claimed', 'Hôm nay đã nhận vé miễn phí.')
            daily['free'] = True; box['tickets'] = box.get('tickets', 0) + 1
            return None, 'Đã nhận 1 vé miễn phí hôm nay.', []
        if op == 'buy_ticket':
            value = _plan(db, [], available); _pay(value, 'cash', TICKET_PRICE)
            box['tickets'] = box.get('tickets', 0) + 1
            return value, f'Đã mua 1 vé ({TICKET_PRICE} Xu).', []
        if box.get('tickets', 0) <= 0:
            raise RewardError('no_ticket', 'Bạn chưa có vé quay. Nhận vé miễn phí hoặc mua thêm.')
        cells = [c for c in _roulettes().get(rtype, []) if c['weight'] > 0]
        pick = random.SystemRandom().choices(cells, weights=[c['weight'] for c in cells])[0]
        value = _plan(db, [dict(kind='item', id=pick['item'], quantity=pick['quantity'])], available)
        box['tickets'] -= 1; box['last'] = pick['id']
        return value, 'Quay trúng!', value['granted']
    row = _find_row(view, key)
    if not row['button']['enabled'] or row['button']['op'] != op:
        raise RewardError('not_available', 'Mục này chưa thể thực hiện hoặc đã nhận.')
    value = _plan(db, row['rewards'], available)
    for cost in row['cost']:
        if cost['kind'] == 'currency':
            _pay(value, cost['id'], cost['quantity'])
        else:
            _take(value['containers'], cost['id'], cost['quantity'])
    message = 'Đã nhận thưởng.'
    if event == 99124:
        st.setdefault('growth', []).append(key)
    elif event == 99007:
        box = st.setdefault('return', {})
        if key == 'pack':
            box['pack'] = True
        else:
            box.setdefault('days', []).append(key); box['last_day'] = _today()
    elif event == 99016:
        _daily(st, 'peak')[key] = True
    elif event == 99042:
        _daily(st, 'online').setdefault('claimed', []).append(key)
    elif event == 99035:
        box = _daily(st, 'group')
        if op == 'buy_share':
            box['shares'] = box.get('shares', 0) + 1; message = 'Đã mua 1 phần.'
        else:
            box['done'] = True
    elif event == 99036:
        box = st.setdefault('fund', {})
        if op == 'buy_fund':
            box['bought'] = _today(); message = 'Đã mua Quỹ Đầu Tư. Nhận Xu mỗi ngày nhé!'
        else:
            box.setdefault('claimed', []).append(key)
    elif event == 309:
        _daily(st, 'mystical').setdefault('bought', []).append(key); message = 'Mua thành công.'
    elif event == 350:
        message = 'Đổi thưởng thành công.'
    elif event == 990040:
        box = st.setdefault('campfire', {})
        if op == 'claim_wood':
            _daily(st, 'campfire_daily')['wood'] = True; box['wood'] = box.get('wood', 0) + WOOD_DAILY
            message = f'Đã nhận {WOOD_DAILY} Củi Lửa Trại.'
        elif op == 'add_wood':
            box['wood'] -= 1; box['fires'] = box.get('fires', 0) + 1; message = 'Lửa trại bùng cháy hơn!'
        else:
            box.setdefault('claimed', []).append(key)
    return value, message, value['granted']


def decode_request(payload):
    if len(payload) < 2:
        raise ValueError('Truncated events request')
    size = struct.unpack_from('<H', payload)[0]
    if size != len(payload) - 2 or size > 8192:
        raise ValueError('Invalid events request frame')
    value = json.loads(payload[2:].decode('utf-8'))
    if (not isinstance(value, dict) or value.get('v') != VERSION or not isinstance(value.get('request_id'), str)
            or not _ID.fullmatch(value['request_id']) or value.get('action') not in ('list', 'act')):
        raise ValueError('Invalid events request')
    if value['action'] == 'act':
        if (type(value.get('event')) is not int or value['event'] not in EVENT_BY_ID
                or not isinstance(value.get('op'), str) or not _KEY.fullmatch(value['op'])
                or not isinstance(value.get('key', ''), str) or not _KEY.fullmatch(value.get('key', ''))):
            raise ValueError('Invalid events action')
    return value


def _reply(value):
    raw = json.dumps(dict(v=VERSION, **value), ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return REPLY, struct.pack('<I', len(raw)) + raw


def apply(state, payload, db):
    """Called by the GATE loop. Returns (packets, error_message_or_None)."""
    request_id = ''
    try:
        request = decode_request(payload)
        request_id = request['request_id']
        if type(state.get('char_id')) is not int or state['char_id'] != storage.profile_id():
            raise RewardError('profile_mismatch', 'Phiên sự kiện không khớp nhân vật.')
        db.execute('BEGIN IMMEDIATE')
        try:
            st = _load(db)
            ctx = dict(level=_n(state.get('level'), 1), containers=inventory.load(db),
                       owned={int(r['tank_id']) for r in db.execute('SELECT tank_id FROM garage WHERE profile_id=?', (storage.profile_id(),))})
            _touch_online(st, time.time())
            packets, result = [], None
            receipt = st['receipts'].get(request_id)
            if request['action'] == 'act' and receipt is not None:
                result = receipt
            elif request['action'] == 'act':
                available = mail_rewards.catalog(db)
                value, message, granted = _act(db, st, ctx, request['event'], request['op'],
                                               request.get('key', ''), available)
                if value is not None:
                    packets = mail_rewards.commit_plan(db, state, value)
                result = dict(event=request['event'], op=request['op'], key=request.get('key', ''),
                              message=message, granted=granted,
                              skipped=(value or {}).get('skipped', []), at=int(time.time()))
                st['receipts'][request_id] = result
                while len(st['receipts']) > 64:
                    st['receipts'].pop(next(iter(st['receipts'])))
                ctx['containers'] = inventory.load(db)
            cosmetic_shop._set(db, SETTING, st)
            views = _views(st, ctx)
            db.commit()
        except BaseException:
            db.rollback()
            raise
        return packets + [_reply(dict(request_id=request_id, ok=True, result=result, events=views))], None
    except (RewardError, ValueError) as exc:
        code = getattr(exc, 'code', 'invalid_request')
        return [_reply(dict(request_id=request_id, ok=False, error=dict(code=code, message=str(exc))))], str(exc)

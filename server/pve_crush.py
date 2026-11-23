"""PvE contact crush: a player tank instantly kills soft infantry it touches.

Native data model (AINpcArmsTemplate / AINpcTemplate):
  iHardness  vehicles/turrets/bosses are 3+, foot soldiers are 2, traps 1
  iRoller=1  explicitly immune (bosses, doors, saws, allied tanks...)
A player tank is a hardness-3 body, so on contact it crushes any moving
enemy NPC whose hardness is lower, unless that NPC is flagged iRoller=1,
is a building, a hostage, or otherwise script-protected. The kill uses the
ordinary damage path with the player's credit, so score, kill stats, drops
and wave progress behave exactly like a normal kill.
"""
from __future__ import annotations

from functools import lru_cache

from combat_data import table_row
from combat_math import D

TANK_HARDNESS = 3
TANK_HALF = 36       # native 72px tank body
TOUCH_SLACK = 6      # blocked bodies stop at the edge; touching counts


@lru_cache(maxsize=4096)
def _profile(template: int):
    """(crushable, half_width, half_height) for an AINpcTemplate id."""
    try:
        row = table_row('AINpcTemplate_table.xml', nTemplateId=template)
        arms = table_row('AINpcArmsTemplate_table.xml', nTemplateId=int(row['nArmsId']))
    except Exception:
        return False, 0, 0
    def number(value, default=0):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default
    hardness = number(arms.get('iHardness'), TANK_HARDNESS)
    crushable = (hardness < TANK_HARDNESS and str(row.get('iRoller') or '').strip() != '1'
                 and str(arms.get('isBuilding') or '').strip() != '1'
                 and number(arms.get('iSpeed')) > 0)
    return crushable, number(arms.get('iWidth'), 48) / 2, number(arms.get('iHeight'), 48) / 2


def _eligible(actor, player) -> bool:
    info = actor.info
    if not info.get('pve_npc') or not actor.alive or actor.camp == player.camp:
        return False
    if (info.get('pve_hostage') or info.get('pve_unscored') or info.get('pve_gate')
            or info.get('pve_boss') or getattr(actor, 'pve_gate', False)):
        return False
    return _profile(int(info.get('npc_template') or 0))[0]


def tick(arena, now) -> list:
    pk = arena.pk
    player = getattr(arena, 'player', None)
    if not pk or pk.get('finished') or player is None or not player.alive or player.in_stasis():
        return []
    px, py = player.position_at(now)
    packets = []
    for actor in list(arena.actors.values()):
        if not _eligible(actor, player):
            continue
        _, hw, hh = _profile(int(actor.info['npc_template']))
        x, y = actor.position_at(now)
        if abs(x - px) > TANK_HALF + hw + TOUCH_SLACK or abs(y - py) > TANK_HALF + hh + TOUCH_SLACK:
            continue
        actor.damage_credit = (player.id, player.generation)
        try:
            packets += actor.commit_hp(D(0), now)
        finally:
            actor.damage_credit = None
        if pk.get('finished'):
            break
    return packets

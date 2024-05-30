"""
Copyright (C) 2016, 2017, 2020 biqqles.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
from typing import Tuple, Optional, Union

from dataclassy import dataclass
from collections import defaultdict

from . import Entity, EntitySet, Equipment
from .. import maps, interface, routines
from ..formats import ini

class Solar(Entity):
    """A solar is something fixed in space (this name comes from the DATA/SOLAR directory)."""
    ids_info = None
    pos: maps.PosVector  # position vector for this solar
    rotate: maps.RotVector = maps.RotVector(0, 0, 0)  # rotation vector for this solar (defaults to no rotation)
    _system: 'System'  # the system this solar resides in

    def sector(self) -> str:
        """The human-readable navmap coordinate (the centre of) this solar resides in."""
        return maps.pos_to_sector(self.pos, self._system.navmapscale)

    def system(self) -> 'System':
        """The entity of the system this solar resides in."""
        return self._system


class Object(Solar):
    """Generic class for a celestial body - a solid object in space. Objects are automatically classified into
    subclasses in `routines.get_system_contents`."""
    archetype: str


class Jump(Object):
    """A jump conduit is a wormhole - artificial or natural - between star systems."""
    goto: Tuple[str, str, str]

    def type(self):
        """Return a human readable name of this jump conduits's type."""
        if 'gate' in self.archetype: return 'Jump Gate'
        if 'jumphole' in self.archetype: return 'Jump Hole'
        if self.archetype == 'entrypoint': return 'Atmospheric Entry'
        return 'Unknown'

    def origin_system(self) -> 'System':
        """The system this wormhole starts in."""
        return self._system

    def destination_system(self) -> 'System':
        """The system this wormhole ends in."""
        destination = self.goto[-1][0] if isinstance(self.goto, list) else self.goto[0]
        return routines.get_systems()[destination]


class TradeLaneRing(Object):
    """A trade lane ring is a component of a trade lane, a structure which provides "superluminal travel" within a
    system."""
    prev_ring: Optional[str] = None
    next_ring: Optional[str] = None
    tradelane_space_name: int = 0


class Wreck(Object):
    """A wreck (called "secrets" in the game files) is a lootable, wrecked ship floating in space."""
    loadout: str  # loot that is dropped upon being shot

    def loadout_(self):
        """This wreck's loadout entity"""
        return routines.get_loadouts()[self.loadout]

    def loot(self):
        return self.loadout_().loot()

@dataclass(slots=False)
class BaseSolar(Object):
    """The physical representation of a Base."""
    reputation: str  # the nickname of the group this base belongs to
    base: str  # the base (in universe.ini) this solar represents

    def universe_base(self) -> 'Base':
        """The Base entity this solar represents."""
        return routines.get_bases().get(self.base)

    def owner(self) -> 'Faction':
        """The Faction entity that operates this base."""
        return routines.get_factions()[self.reputation]

    def infocard(self, markup='html') -> str:
        """Base infocards are actually in two parts, with ids_info referring to the specs of a base and ids_info + 1
        storing the actual description"""
        lookup = self._markup_formats[markup]

        specifications = lookup(self.ids_info)
        try:
            synopsis = lookup(interface.get_infocardmap().get(self.ids_info))
            # if not synopsis:
            #     synopsis = lookup(self.ids_info + 1)
            return specifications + '<p >' + synopsis
        except KeyError:
            return specifications

    def infocard2(self, markup='html') -> str:
        """Base infocards are actually in two parts, with ids_info referring to the specs of a base and ids_info + 1
        storing the actual description"""
        lookup = self._markup_formats[markup]

        specifications = '<p>'
        try:
            synopsis = lookup(interface.get_infocardmap().get(self.ids_info))
            if not synopsis:
                return False
                synopsis = lookup(self.ids_info + 1)
            return True
            return specifications + '<p >' + synopsis
        except KeyError:
            return specifications


class Spheroid(Object):
    """A star or planet. (Abstract.)"""
    atmosphere_range: int = 0


class Star(Spheroid):
    """A star in a System."""
    star: str


@dataclass(slots=False)
class Planet(Spheroid):
    """A planet in a System."""
    spin: Optional[Tuple[float, float, float]] = (0. ,0. ,0.)


class PlanetaryBase(Planet, BaseSolar):
    """A base on the surface of a planet, typically accessible via a docking ring."""


class Zone(Solar):
    """A zone is a region of space, possibly with effects attached."""
    size: Union[int, Tuple[int, int], Tuple[int, int, int]]
    shape: str  # one of: sphere, ring, box, ellipsoid


class Loadout(Entity):
    nickname: str
    archetype: Optional[str] = None
    cargo: tuple((str, int)) = None # (nickname, amount)

    def loot(self) -> EntitySet['Equipment']:
        result = []
        if type(self.cargo) is not list and self.cargo:
            self.cargo = [self.cargo]

        if self.cargo:
            for equip in self.cargo:
                if not type(equip) == tuple:
                    equip = [equip, 1]

                result.append([routines.get_equipment()[equip[0]], equip[1]])
        
        default = defaultdict(int, dict(result))
        
        for e in default:
            if [i[0] for i in result].count(e) > 1:
                default[e] = [i[0] for i in result].count(e)

        return [[x, y] for x, y in dict(default).items()]


from .universe import Base, Faction, System
from .. import routines

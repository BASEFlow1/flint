"""
Copyright (C) 2016, 2017, 2020 biqqles.
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import os

from dataclassy import Internal

from ..formats import dll
from .. import paths, routines, missions
from . import Entity, EntitySet
from .solars import BaseSolar, Wreck
from .equipment import Equipment, Commodity
from .ship import Ship
from .goods import EquipmentGood, CommodityGood, ShipPackage


class System(Entity):
    """A star system."""
    file: str
    navmapscale: float = 1.0

    def definition_path(self) -> str:
        """The absolute path to the file that defines this system's contents."""
        return paths.construct_path(os.path.dirname(paths.inis['universe'][0]), self.file)

    def contents(self) -> 'EntitySet[Solar]':
        """All solars in this system."""
        return routines.get_system_contents(self, False)
    
    def contents_raw(self) -> 'list':
        """All solars in this system."""
        return routines.get_system_contents(self, True)

    def wrecks(self) -> 'EntitySet[Wreck]':
        """All wrecks in this system"""
        return self.contents().of_type(Wreck)

    def zones(self) -> 'EntitySet[Zone]':
        """All zones in this system."""
        return self.contents().of_type(Zone)

    def objects(self) -> 'EntitySet[Object]':
        """All objects in this system."""
        return self.contents().of_type(Object)

    def bases(self) -> 'EntitySet[BaseSolar]':
        """All bases in this system."""
        return self.contents().of_type(BaseSolar)

    def planets(self) -> 'EntitySet[Planet]':
        """All planets in this system."""
        return self.contents().of_type(Planet)

    def stars(self) -> 'EntitySet[Star]':
        """All stars in this system."""
        return self.contents().of_type(Star)

    def connections(self) -> 'Dict[Jump, System]':
        """The connections this system has to other systems."""
        return {c: c.destination_system() for c in self.contents().of_type(Jump)}

    def lanes(self) -> 'List[List[TradeLaneRing]]':
        """Return a list of lists of rings, where each nested list represents a complete trade lane and contains each
        ring in that lane in order."""
        rings = EntitySet(c for c in self.contents() if isinstance(c, TradeLaneRing))
        lanes = {r: [] for r in rings if r.prev_ring is None}  # find rings which start a lane
        # group remaining rings into one of these
        for first_ring in lanes:
            current_ring = first_ring
            while current_ring:
                if current_ring.next_ring:
                    current_ring = rings.get(current_ring.next_ring)
                    if current_ring:
                        lanes[first_ring].append(current_ring)
                else:
                    break
        return [[f, *r] for f, r in lanes.items()]  # flatten grouping dict into list of lists

    def region(self) -> str:
        """The name of the region this system is in, extracted from the infocard."""
        *_, rest = self.infocard('rdl').partition('<TRA data="1" mask="1" def="-2"/><TEXT>')
        region, *_ = rest.partition('</TEXT>')
        return region.title() if region else 'Unknown'


class Base(Entity):
    """A space station or colonised planet, operated by a Faction."""
    ids_info = None  # infocard is defined by the base's solar
    system: str

    def infocard(self, markup='html') -> str:
        """The infocard of this base's solar (Base sections do not define ids_info)."""
        return self.solar().infocard(markup)

    def system_(self) -> System:
        """The entity of the system this base resides in."""
        return routines.get_systems()[self.system]

    def solar(self) -> Optional['BaseSolar']:
        """Confusingly, Freelancer defines bases separately to their physical representation."""
        return self.system_().bases().unique(base=self.nickname)

    def has_solar(self) -> bool:
        """Whether this base has a physical solar."""
        return self.solar() is not None

    def mbase(self) -> Optional[missions.MBase]:
        """The mission base entry for this base."""
        return missions.get_mbases().get(self.nickname)

    def bribes(self):
        """The bribes offered on this base."""
        if self.mbase():
            npcs = self.mbase().npcs
            bribes = [npc.bribe if type(npc.bribe) == list else [npc.bribe] for npc in npcs]
            factions = []
            bribes = [elem for sublist in bribes for elem in sublist]
            bribes = list(filter(None, bribes))
            for faction in bribes:
                try:
                    factions.append(faction[0])
                except KeyError:
                    pass
            factions = list(dict.fromkeys(factions))
            facts = []
            for x in factions:
                try:
                    facts.append(routines.get_factions()[x])
                except KeyError:
                    pass
            return EntitySet(facts)
    
    def missions(self):
        """The factions offering missions on this base."""
        factions = []
        if self.mbase():
            for faction in self.mbase().factions:
                    if faction.mission_type and type(faction.faction) != list:
                        factions.append(faction.faction)
                    elif faction.mission_type:
                        for fact, offers in zip(faction.faction, faction.offers_missions):
                            if offers:
                                factions.append(fact)
        return EntitySet(routines.get_factions()[x] for x in factions)

    def factions(self) -> list:
        """All factions present on this base"""
        if self.mbase():
            return EntitySet(routines.get_factions()[fact.faction] for fact in [entry for entry in self.mbase().factions])
 
    def rumors(self, markup='html') -> Dict[str, Set[str]]:
        """All rumors offered on this base, of the form {faction -> rumors}"""
        lookup = self._markup_formats[markup]
        if self.mbase():
            rumors = defaultdict(set)
            npcs = self.mbase().npcs

            for npc in npcs:
                if npc.rumor:
                    if type(npc.rumor) is not list:
                        npc.rumor = [npc.rumor]
                    
                    rumors[routines.get_factions()[npc.affiliation]].update(
                        lookup(rumor_id) for *_, rumor_id in npc.rumor
                    )
            return dict(rumors)
        return {}

    def news(self):
        """A list of all news items being shown on this base"""
        return missions.get_news().get(self.nickname, [])


    def owner(self) -> 'Faction':
        """The faction which owns this base (its IFF)."""
        return self.solar().owner() if self.has_solar() \
            else routines.get_factions()[self.mbase().local_faction] if self.mbase() else None

    def sector(self) -> str:
        """The sector of this base's solar in its system."""
        return self.solar().sector()

    def market(self):
        return routines.get_markets()[self]

    def sells(self) -> Dict['Good', int]:
        """The goods this base sells, of the form {good -> price}."""
        return self.market()[True]

    def buys(self) -> Dict['Good', int]:
        """The goods this base buys, of the form {good -> price}"""
        return self.market()[False]

    def sells_commodities(self) -> Dict[Commodity, int]:
        """The commodities represented by the goods this base sells, mapped to their prices."""
        return {good.commodity(): price for good, price in self.sells().items() if isinstance(good, CommodityGood)}

    def buys_commodities(self) -> Dict[Commodity, int]:
        """The commodities represented by the goods this base buys, mapped to their prices."""
        return {good.commodity(): price for good, price in self.buys().items() if isinstance(good, CommodityGood)}

    def sells_equipment(self) -> Dict[Equipment, int]:
        """The equipment represented by the goods this base sells, mapped to their prices."""
        return {good.equipment_(): price for good, price in self.sells().items() if type(good) is EquipmentGood}

    def sells_ships(self) -> Dict[Ship, int]:
        """The ships represented by the goods this base sells, mapped to their cost."""
        return {good.ship(): good.cost() for good in self.sells() if isinstance(good, ShipPackage)}


class Faction(Entity):
    """A faction, also known as a group, is an organisation in the Freelancer universe, possibly owning bases or
    controlling territory."""
    ids_short_name: int  # resource id for short form name
    rep: Internal[List[Tuple[float, str]]]  # float is between 1 (adored) and -1 (reviled)

    def short_name(self) -> str:
        """The short form of this faction's name."""
        return dll.lookup(self.ids_short_name)

    def bases(self) -> EntitySet[Base]:
        """All bases owned by this faction."""
        return EntitySet(base for base in routines.get_bases() if base.has_solar() and base.solar().reputation == self.nickname)

    def rep_sheet(self) -> Dict['Faction', float]:
        """How this faction views other factions - its reputation sheet."""
        factions = routines.get_factions()
        return {factions[faction]: rep for rep, faction in self.rep if faction in factions}

    def can_dock_at(self, base: BaseSolar) -> bool:
        """Whether this faction can dock at the given base."""
        return self.rep_sheet()[base.owner()] > self.NODOCK_REP

    def props(self) -> missions.FactionProps:
        """The FactionProps entry for this faction."""
        return missions.get_faction_props()[self.nickname]

    def legality(self) -> str:
        """The legality of this faction as defined in its FactionProps entry (Lawful or Unlawful)."""
        return self.props().legality.capitalize()

    def ships(self) -> EntitySet[Ship]:
        """All ships this faction uses, as defined in faction_props.ini"""
        result = []
        npc_ship = self.props().npc_ship if type(self.props().npc_ship) == list else [self.props().npc_ship]

        for x in npc_ship:
            if routines.get_npcships()[x].ship():
                result.append(routines.get_npcships()[x].ship())

        return EntitySet(result)

    def bribes(self) -> EntitySet[Base]:
        """EntitySet of bases that offer bribes/rep hacks for this faction"""
        result = set()

        for base in routines.get_bases():
            try:
                if base.has_solar():
                    if self.nickname in base.bribes():
                        result.add(base)
            except TypeError:
                pass

        return EntitySet(result)

    def rumors(self) -> dict:
        """All rumors this faction offers mapped to the bases they are offered on"""
        result = {}
        for base in routines.get_bases():
            try:
                if base.has_solar():
                    if self in base.rumors().keys():
                        result[base.nickname] = base.rumors()[self]
            except AttributeError:
                pass

        return result

    NODOCK_REP = -0.65


from .solars import Solar, BaseSolar, Jump, Planet, Star, Zone, Object, TradeLaneRing

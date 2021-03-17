#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gazetteer class for Campā parser
"""

from campa.geography.indexing import PlaceIndexByName
from campa.geography.logger import SelfLogger
from pprint import pprint


class Gazetteer(SelfLogger):

    def __init__(self):
        super().__init__()
        self.places = {}
        self.catalog = {
            'names2pids': PlaceIndexByName()
        }

    def set_place(self, place, overwrite=False):
        """Add a place to the gazetteer"""
        logger = self._get_logger()
        try:
            prior = self.places[place.pid]
        except KeyError:
            self.places[place.pid] = place
            msg = (
                'Added new place entry to gazetteer:\n'
                '\t{}: {} ({})'
                ''.format(place.pid, ', '.join(place.names), '/'.join(place.types))
            )
            logger.info(msg)
        else:
            if overwrite:
                logger.warning(
                    'Overwriting {}'.format(place.pid)
                )
                self.places[place.pid] = place
            else:
                if place == prior:
                    raise RuntimeError('joy')
                else:
                    if dir(prior) != dir(prior):
                        raise NotImplementedError('field name mismatch')
                    for k, v in prior.__dict__.items():
                        new_v = getattr(place, k)
                        if v != new_v:
                            raise NotImplementedError(
                                '{}: {} vs. {}'.format(k, v, new_v))
                    
            return
        self.catalog['names2pids'].add(place)

    def lookup(self, term):
        """Lookup term using pids and names"""
        logger = self._get_logger()
        hit = None
        try:
            hit = self.places[term]
        except KeyError:
            pids = self.catalog['names2pids'].lookup(term)
            if len(pids) > 1:
                raise NotImplementedError(pids)
            elif len(pids) == 1:
                try:
                    hit = self.places[pids[0]]
                except KeyError:
                    pass
            
        if hit is None:
            raise LookupError('Could not find {}'.format(term))
        else:
            return hit



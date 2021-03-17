#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gazetteer class for Campā parser
"""

from geography.indexing import PlaceIndexByName
from geography.logger import SelfLogger
import logging


class Gazetteer(SelfLogger):

    def __init__(self):
        super().__init__()
        self.places = {}
        self.catalog = {
            'names2pids': PlaceIndexByName()
        }

    def set_place(self, place, overwrite=False):
        """Add a place to the gazetteer"""
        try:
            self.places[place.pid]
        except KeyError:
            self.places[place.pid] = place
        else:
            if overwrite:
                logger.warning(
                    'Overwriting {}'.format(place.pid)
                )
                self.places[place.pid] = place
            else:
                raise NotImplementedError(
                    'place collision: pid={}'.format(place.pid))
            return
        self.catalog['names2pids'].add(place)

    def lookup(self, term):
        """Lookup term using pids and names"""
        try:
            hit = self.places[term]
        except KeyError:
            try:
                hit = self.places[self.catalog['names2pids'].lookup(term)]
            except KeyError:
                hit = None
        if hit is None:
            raise LookupError('Could not find {}'.format(term))
        else:
            return hit



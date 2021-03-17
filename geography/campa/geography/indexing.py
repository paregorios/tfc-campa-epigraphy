#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Indexing classes
"""

from campa.geography.logger import SelfLogger
from textnorm import normalize_space, normalize_unicode


def norm(raw):
    return normalize_unicode(normalize_space(raw))


class CatalogIndex(SelfLogger):

    def __init__(self, title):
        super().__init__()
        self.title = title
        self.index = {}
        self.reverse_index = {}

    def set_term(self, term, targets):
        if isinstance(targets, str):
            target_list = [targets]
        elif isinstance(targets, list):
            target_list = targets
        else:
            raise TypeError(
                'targets is {} expected "list" or "str"'.format(type(targets)))
        nterm = self._norm_term(term)
        try:
            self.index[nterm]
        except KeyError:
            self.index[nterm] = target_list
        else:
            self.index[nterm].extend(target_list)
        self.index[nterm] = list(set(self.index[nterm]))
        for t in target_list:
            nt = self._norm_term(t)
            try:
                self.reverse_index[nt]
            except KeyError:
                self.reverse_index[nt] = []
            if term not in self.reverse_index[nt]:
                self.reverse_index[nt].append(term)
            self.reverse_index[nt] = list(set(self.reverse_index[nt]))

    def lookup(self, term):
        return self.index[self._norm_term(term)]

    def lookup_reverse(self, target):
        return self.reverse_index[self._norm_term(target)]

    def _norm_term(self, raw):
        cooked = norm(raw)
        return '-'.join(cooked.lower().split())


class PlaceIndexByName(CatalogIndex):

    def __init__(self):
        super().__init__('PlaceIndexByName')

    def add(self, place):
        for name in place.names:
            self.set_term(name, place.pid)

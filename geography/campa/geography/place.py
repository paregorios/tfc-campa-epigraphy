#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Campa Place type
"""

from campa.geography.logger import SelfLogger
from pprint import pformat, pprint
import re
import sys


class CampaPlace(SelfLogger):

    def __init__(self, pid, gazetteer=None, **kwargs):
        logger = self._get_logger()
        self.pid = pid
        if gazetteer is not None:
            self.gazetteer = gazetteer
        for k, v in kwargs.items():
            kfn = '_'.join(k.lower().split())
            try:
                getattr(self, 'set_{}'.format(kfn))(v)
            except AttributeError:
                logger.error(pformat(kwargs, indent=4))
                raise

    def set_aliases(self, value):
        # wikidata alternate lookups
        pass
    
    def set_alpha_2(self, value):
        self._set_identifier('ISO 3166-1', 'alpha-2', value)

    def set_alpha_3(self, value):
        self._set_identifier('ISO 3166-1', 'alpha-3', value)

    def set_alternate_name(self, value):
        self.set_name(value)

    def set_cnumber(self, value):
        try:
            self.cnumbers
        except AttributeError:
            self.cnumbers = []
        self.cnumbers.append(value)

    def set_code(self, value):
        self._set_identifier('ISO 3166-2', value)

    def set_common_name(self, value):
        self.set_name(value)

    def set_commune(self, value):
        if value:
            self.commune = self._set_with_gazetteer(value)

    def set_concepturi(self, value):
        self.set_same_as([value])

    def set_country(self, value):
        if value:
            self.country = self._set_with_gazetteer(value)

    def set_country_code(self, value):
        pass
    
    def set_description(self, value):
        if value in ['city']:
            self.set_type(value)
        elif value.startswith('capital of '):
            self.set_type('city')
            self.description = value
        else:
            raise NotImplementedError(
                'description: {}'.format(value))

    def set_district(self, value):
        if value:
            self.district = self._set_with_gazetteer(value)

    def set_id(self, value):
        m = re.match(r'^Q\d+$', value)
        if m is not None:
            self._set_identifier('wikidata', value)

    def set_label(self, value):
        self.set_name(value)

    def set_match(self, value):
        pass

    def set_name(self, value):
        try:
            self.names
        except AttributeError:
            self.names = []
        if value not in self.names:
            self.names.append(value)

    def set_numeric(self, value):
        self._set_identifier('ISO 3166-1', 'numeric', value)        

    def set_official_name(self, value):
        self.set_name(value)

    def set_pageid(self, value):
        pass

    def set_parent_code(self, value):
        if value is None:
            return
        raise NotImplementedError('parent_code')

    def set_position(self, value):
        if value:
            self.position = self._set_with_gazetteer(value)

    def set_project_name(self, value):
        self.set_name(value)

    def set_province(self, value):
        if value:
            self.province = self._set_with_gazetteer(value)

    def set_ptype(self, value):
        self.set_type(value)

    def set_repository(self, value):
        pass

    def set_same_as(self, values):
        try:
            self.same_as
        except AttributeError:
            self.same_as = []
        for value in values:
            if value not in self.same_as:
                self.same_as.append(value)

    def set_title(self, value):
        self.set_name(value)

    def set_type(self, value):
        try:
            self.types
        except AttributeError:
            self.types = []
        if value not in self.types and value.lower() not in self.types:
            self.types.append(value)

    def set_types(self, values):
        if isinstance(values, str):
            self.set_type(values)
        else:
            try:
                self.types
            except AttributeError:
                self.types = []
            for value in values:
                if value not in self.types and value.lower() not in self.types:
                    self.types.append(value)

    def set_uris(self, values):
        try:
            self.uris
        except AttributeError:
            self.uris = []
        for value in values:
            if value.startswith('//'):
                value = 'https:' + value
            if value not in self.uris:
                self.uris.append(value)

    def set_url(self, value):
        self.set_uris([value])

    def set_village(self, value):
        self.village = self._set_with_gazetteer(value)

    def _set_identifier(self, *values):
        try:
            self.identifiers
        except AttributeError:
            self.identifiers = {}
        d = self.identifiers
        prev = d
        for i, value in enumerate(values):
            if len(values) == 1:
                raise ValueError(values)
            elif i == len(values) - 1:
                prev.append(value)
            elif i == len(values) - 2:
                try:
                    prev[value]
                except KeyError:
                    prev[value] = []
                prev = prev[value]
            else:
                try:
                    prev[value]
                except KeyError:
                    prev[value] = {}
                prev = prev[value]

    def _set_with_gazetteer(self, value):
        result = {'name': value}
        try:
            place = self.gazetteer.lookup(value)
        except (AttributeError, KeyError):
            pass
        else:
            result['pid'] = place.pid
        return result

        
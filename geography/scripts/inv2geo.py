#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert Campā inventory to geodata
"""

from airtight.cli import configure_commandline
from encoded_csv import get_csv
import inspect
import json
import logging
from logging import debug, info, warning, error, fatal
from pathlib import Path
from pprint import pformat, pprint
import pycountry
import re
import sys
from textnorm import normalize_space, normalize_unicode
from wikidata.client import Client as wdClient
from wikidata_suggest import suggest

DEFAULT_LOG_LEVEL = logging.WARNING
OPTIONAL_ARGUMENTS = [
    ['-l', '--loglevel', 'NOTSET',
        'desired logging level (' +
        'case-insensitive string: DEBUG, INFO, WARNING, or ERROR',
        False],
    ['-v', '--verbose', False, 'verbose output (logging level == INFO)',
        False],
    ['-w', '--veryverbose', False,
        'very verbose output (logging level == DEBUG)', False],
    ['-d', '--districts', 'districts.json', 'districts info', False],
    ['-c', '--communes', 'communes.json', 'communes info', False]
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
    ['infile', str, 'input CSV file']
]


def norm(raw):
    return normalize_unicode(normalize_space(raw))


class CatalogIndex(object):

    def __init__(self, title):
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


class CampaPlace(object):

    def __init__(self, pid, **kwargs):
        self.pid = pid
        for k, v in kwargs.items():
            kfn = '_'.join(k.lower().split())
            getattr(self, 'set_{}'.format(kfn))(v)

    def set_alpha_2(self, value):
        self._set_identifier('ISO 3166-1', 'alpha-2', value)

    def set_alpha_3(self, value):
        self._set_identifier('ISO 3166-1', 'alpha-3', value)

    def set_code(self, value):
        self._set_identifier('ISO 3166-2', value)

    def set_id(self, value):
        m = re.match(r'^Q\d+$', value)
        if m is not None:
            self._set_identifier('wikidata', value)

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

    def set_numeric(self, value):
        self._set_identifier('ISO 3166-1', 'numeric', value)        

    def set_common_name(self, value):
        self.set_name(value)

    def set_concepturi(self, value):
        self.set_same_as([value])

    def set_country_code(self, value):
        if value is not None:
            self.country_code = value

    def set_description(self, value):
        if value in ['city']:
            self.set_type(value)
        else:
            raise NotImplementedError(
                'description: {}'.format(value))

    def set_match(self, value):
        pass

    def set_official_name(self, value):
        self.set_name(value)

    def set_label(self, value):
        self.set_name(value)

    def set_name(self, value):
        try:
            self.names
        except AttributeError:
            self.names = []
        if value not in self.names:
            self.names.append(value)

    def set_pageid(self, value):
        pass

    def set_parent_code(self, value):
        if value is None:
            return
        raise NotImplementedError('parent_code')

    def set_project_name(self, value):
        self.set_name(value)

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
        

class Gazetteer(object):

    def __init__(self):
        self.places = {}
        self.catalog = {
            'names2pids': PlaceIndexByName()
        }

    def set_place(self, place, overwrite=False):
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
                logger.info(
                    'Place {} already exists; not overwriting.'
                    ''.format(place.pid)
                )
            return
        self.catalog['names2pids'].add(place)

    def lookup(self, term):
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


class PlaceParser(object):

    def __init__(self, districts, communes):
        self.cache = {}
        self.wd_client = wdClient()
        self.districts_path = str(districts)
        self.communes_path = str(communes)
        logger = self._get_logger()
        with districts.open('r', encoding='utf-8') as f:
            self.districts = json.load(f)
        del f
        logger.debug(
            'read {} districts from {}'
            ''.format(len(self.districts), districts))
        with communes.open('r', encoding='utf-8') as f:
            self.communes = json.load(f)
        del f
        logger.debug(
            'read {} communes from {}'
            ''.format(len(self.communes), communes))

    def _get_logger(self):
        name = ':'.join((
            self.__class__.__name__,
            sys._getframe().f_back.f_code.co_name))
        return logging.getLogger(name)

    def parse(self, **kwargs):
        logger = self._get_logger()
        logger.debug('kwargs:\n%s', pformat(kwargs, indent=4))
        places = []
        for k, v in kwargs.items():
            places.append(getattr(self, '_parse_{}'.format(k))(**kwargs))
        return [p for p in places if p is not None]

    def _parse_cnumber(self, **kwargs):
        pass

    def _parse_commune(self, **kwargs):
        commune_name = kwargs['commune']
        logger = self._get_logger()
        if not self._present('commune', commune_name):
            return
        try:
            commune = self.communes[commune_name]
        except KeyError:
            print('Attempting to get additional information about "{}"'.format(commune_name))
            wikidata = suggest(commune_name)
            logger.debug(pformat(wikidata, indent=4))
            if wikidata is not None:
                self.communes[commune_name] = wikidata
                self._save_communes()
                commune = wikidata
        else:
            logger.debug('using stored wikidata commune information')
        logger.debug('wikidata:\n%s', pformat(commune, indent=4))
        commune_slug = '-'.join(
            re.sub(r'[()-_]+', '', norm(commune_name).lower()).split())
        if commune is not None:
            p = CampaPlace(
                pid=commune_slug,
                types=['commune', 'ADM4'],
                project_name=commune_name,
                **commune
            )
        logger.debug('CampaPlace:\n%s', pformat(p.__dict__, indent=4))
        return p

    def _parse_country(self, **kwargs):
        country_name = kwargs['country']
        logger = self._get_logger()
        if not self._present('country', country_name):
            return
        try:
            country = self.cache[country_name]
        except KeyError:
            country = pycountry.countries.lookup(country_name)
            logger.debug(
                'pycountry:country:\n%s', pformat(country.__dict__['_fields'], indent=4))
        p = CampaPlace(
            pid=country.alpha_2, 
            types=['country', 'ADM1'],
            project_name=country_name,
            **country.__dict__['_fields'])
        logger.debug('CampaPlace:\n%s', pformat(p.__dict__, indent=4))
        return p

    def _parse_district(self, **kwargs):
        district_name = kwargs['district']
        logger = self._get_logger()
        if not self._present('district', district_name):
            return
        district = None
        try:
            district = self.districts[district_name]
        except KeyError:
            wikidata = suggest(district_name)
            logger.debug(pformat(wikidata, indent=4))
            if wikidata is not None:
                self.districts[district_name] = wikidata
                self._save_districts()
                district = wikidata
        else:
            logger.debug('using stored wikidata district information')
        logger.debug('wikidata:\n%s', pformat(district, indent=4))
        district_slug = '-'.join(
            re.sub(r'[()-_]+', '', norm(district_name).lower()).split())
        if district is not None:
            p = CampaPlace(
                pid=district_slug,
                types=['district', 'ADM3'],
                project_name=district_name,
                **district
            )
        logger.debug('CampaPlace:\n%s', pformat(p.__dict__, indent=4))
        return p
            
    def _parse_position(self, **kwargs):
        position_name = kwargs['position']
        if not self._present('position', position_name):
            return
        raise NotImplementedError(inspect.currentframe.f_code.co_name)
        
    def _parse_province(self, **kwargs):
        province_name = kwargs['province']
        logger = self._get_logger()
        if not self._present('province', province_name):
            return
        try:
            province = self.cache[province_name]
        except KeyError:
            province = pycountry.subdivisions.lookup(province_name)
            logger.debug(
                'pycountry:subdivision:\n%s', 
                pformat(province.__dict__['_fields'], indent=4))
        p = CampaPlace(
            pid=province.code,
            types=['province', 'tỉnh', 'ADM2'],
            project_name=province_name,
            **province.__dict__['_fields'])
        logger.debug('CampaPlace:\n%s', pformat(p.__dict__, indent=4))
        return p

    def _parse_village(self, **kwargs):
        village_name = kwargs['village']
        if not self._present('village', village_name):
            return
        raise NotImplementedError(inspect.currentframe.f_code.co_name)
        
    def _present(self, field_name, value):
        if value == '':
            logger = self._get_logger()
            logger.warning('IGNORED: %s (%s)', field_name, 'empty string')
            return False
        return value

    def _save_communes(self):
        communes = Path(self.communes_path)
        communes.rename(self.communes_path + '.bak')
        communes = Path(self.communes_path)
        with communes.open('w', encoding='utf-8') as fp:
            json.dump(self.communes, fp, indent=4, ensure_ascii=False)
        del fp

    def _save_districts(self):
        districts = Path(self.districts_path)
        districts.rename(self.districts_path + '.bak')
        districts = Path(self.districts_path)
        with districts.open('w', encoding='utf-8') as fp:
            json.dump(self.districts, fp, indent=4, ensure_ascii=False)
        del fp


def main(**kwargs):
    """
    main function
    """
    global logger
    logging.basicConfig(format='%(levelname)s:%(message)s')
    logger = logging.getLogger(__package__)
    data = get_csv(kwargs['infile'])
    logger.debug('CSV fieldnames: %s', data['fieldnames'])
    logger.info('Rows in CSV file: %s', len(data['content']))
    g = Gazetteer()
    districts = kwargs['districts']
    if districts == 'districts.json':
        dpath = Path(__file__).parent.parent / districts
    else:
        dpath = Path(districts).expanduser().resolve()
    logger.info('Path to districts file: %s', str(dpath))
    communes = kwargs['communes']
    if communes == 'communes.json':
        cpath = Path(__file__).parent.parent / communes
    else:
        cpath = Path(communes).expanduser().resolve()
    p = PlaceParser(dpath, cpath)
    for row in data['content']:
        # country -> province -> district -> commune -> village -> position
        clean_data = {
            'cnumber': norm(row['N° C.']),
            'country': norm(row['Pays']),
            'province': norm(row['Province  (Tỉnh, Thành Phố)']),
            'district': norm(row['District (Huyện ou Thì xã)']),
            'commune': norm(row['Commune  (Xã)']),
            'village': norm(row['Village  (Thôn)']),
            'position': norm(row['Position'])
        }
        places = p.parse(**clean_data)
        for place in places:
            g.set_place(place)
            

if __name__ == "__main__":
    main(**configure_commandline(
        OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))

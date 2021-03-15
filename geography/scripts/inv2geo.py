#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert Campā inventory to geodata
"""

from airtight.cli import configure_commandline
from encoded_csv import get_csv
import inspect
import logging
from pprint import pformat, pprint
import pycountry
import sys
from textnorm import normalize_space, normalize_unicode

logger = logging.getLogger(__name__)

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
            self.index.extend(target_list)
        self.index = list(set(self.index))
        for t in target_list:
            nt = self._norm_term(t)
            try:
                self.reverse_index[nt]
            except KeyError:
                self.reverse_index[nt] = []
            if term not in self.reverse_index[nt]:
                self.reverse_index.append(term)

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

    def index(self, place):
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

    def set_country_code(self, value):
        if value is not None:
            self.country_code = value

    def set_official_name(self, value):
        self.set_name(value)

    def set_name(self, value):
        try:
            self.names
        except AttributeError:
            self.names = []
        if value not in self.names:
            self.names.append(value)

    def set_parent_code(self, value):
        if value is None:
            return
        raise NotImplementedError('parent_code')

    def set_project_name(self, value):
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
        self.catalog['names2pids'].index(place)

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

    def __init__(self):
        self.cache = {}

    def parse(self, **kwargs):
        logger_name = ':'.join((
            self.__class__.__name__,
            inspect.currentframe().f_code.co_name,
            '\nkwargs'))
        logger = logging.getLogger(logger_name)
        logger.debug('\n' + pformat(kwargs, indent=4))
        places = []
        for k, v in kwargs.items():
            places.append(getattr(self, '_parse_{}'.format(k))(**kwargs))
        return places

    def _parse_cnumber(self, **kwargs):
        pass

    def _parse_country(self, **kwargs):
        country_name = kwargs['country']
        if country_name == '':
            logger_name = ':'.join((
                self.__class__.__name__,
                inspect.currentframe().f_code.co_name))
            logger = logging.getLogger(logger_name)
            logger.warning(
                'IGNORED: No country for Campā Inscription Number {}'
                ''.format(kwargs['cnumber']))
            return
        try:
            country = self.cache[country_name]
        except KeyError:
            country = pycountry.countries.lookup(country_name)
            logger_name = ':'.join((
                self.__class__.__name__,
                inspect.currentframe().f_code.co_name,
                '\nCountry'))
            logger = logging.getLogger(logger_name)
            logger.debug('\n' + pformat(country.__dict__['_fields'], indent=4))
        p = CampaPlace(
            pid=country.alpha_2, 
            types=['country', 'ADM1'],
            project_name=country_name,
            **country.__dict__['_fields'])
        logger_name = ':'.join((
            self.__class__.__name__,
            inspect.currentframe().f_code.co_name,
            '\n{}'.format(p.__class__.__name__)))
        logger = logging.getLogger(logger_name)
        logger.debug('\n' + pformat(p.__dict__, indent=4))

    def _parse_province(self, **kwargs):
        province_name = kwargs['province']
        if province_name == '':
            logger_name = ':'.join((
                self.__class__.__name__,
                inspect.currentframe().f_code.co_name))
            logger = logging.getLogger(logger_name)
            logger.warning(
                'IGNORED: No province for Campā Inscription Number {}'
                ''.format(kwargs['cnumber']))
            return
        try:
            province = self.cache[province_name]
        except KeyError:
            province = pycountry.subdivisions.lookup(province_name)
            logger_name = ':'.join((
                self.__class__.__name__,
                inspect.currentframe().f_code.co_name,
                '\nProvince'))
            logger = logging.getLogger(logger_name)
            logger.debug('\n' + pformat(province.__dict__['_fields'], indent=4))
        p = CampaPlace(
            pid=province.code,
            types=['province', 'tỉnh', 'ADM2'],
            project_name=province_name,
            **province.__dict__['_fields'])
        logger_name = ':'.join((
            self.__class__.__name__,
            inspect.currentframe().f_code.co_name,
            '\n{}'.format(p.__class__.__name__)))
        logger = logging.getLogger(logger_name)
        logger.debug('\n' + pformat(p.__dict__, indent=4))

def main(**kwargs):
    """
    main function
    """
    logger = logging.getLogger(sys._getframe().f_code.co_name)
    data = get_csv(kwargs['infile'])
    logger.info(data['fieldnames'])
    logger.info('Rows in file: {}'.format(len(data['content'])))
    g = Gazetteer()
    p = PlaceParser()
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
            g.set_place(p)
            

if __name__ == "__main__":
    main(**configure_commandline(
        OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert Campā inventory to geodata
"""

from airtight.cli import configure_commandline
from colorama import Fore, Style
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
    ['-c', '--communes', 'communes.json', 'communes info', False],
    ['-t', '--villages', 'villages.json', 'villages info', False]
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
    ['infile', str, 'input CSV file']
]






class PlaceParser(object):

    def __init__(self, districts, communes, villages):
        self.cache = {}
        self.wd_client = wdClient()
        self.districts_path = str(districts)
        self.communes_path = str(communes)
        self.villages_path = str(villages)
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
        with villages.open('r', encoding='utf-8') as f:
            self.villages = json.load(f)
        del f
        logger.debug(
            'read {} villages from {}'
            ''.format(len(self.villages), villages))

    def parse(self, **kwargs):
        logger = self._get_logger()
        logger.debug('kwargs:\n%s', pformat(kwargs, indent=4))
        places = []
        keys = ['country', 'province', 'district', 'commune', 'village', 'position']
        for k in keys:
            v = kwargs[k]
            try:
                place = getattr(self, '_parse_{}'.format(k))(**kwargs)
            except LookupError:
                msg = (
                    'LOOKUP FAILED for "{}" as a "{}"'
                    ''.format(v, k))
                if k != 'country':
                    msg += ' in {}'.format(kwargs['country'])
                if k != 'cnumber':
                    msg += ' (C{})'.format(kwargs['cnumber'])
                logger.warning(msg)
                place = self._make_place(name=v, ptype=k)
            else:
                places.append(place)
        return [p for p in places if p is not None]

    def _make_place(self, pid='slug', **kwargs):
        try:
            kwargs['ptype']
        except KeyError:
            types = []
        else:
            t = kwargs['ptype']
            types = [t]
            if t == 'country':
                types.append('ADM1')
            elif t == 'province':
                types.append('ADM2')
            elif t == 'district':
                types.append('ADM3')
            elif t == 'commune':
                types.append('ADM4')
            elif t == 'village':
                types.append('PPA')
        if pid == 'slug':
            name = kwargs['name']
            slug = '-'.join(
                re.sub(r'[()-_]+', '', norm(name).lower()).split())
            p = CampaPlace(pid=slug, types=types, **kwargs)
        else:
            p = CampaPlace(pid=pid, types=types, **kwargs)
        return p

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
            if country_name == 'Cambodge':
                lookup = 'Cambodia'
            else:
                lookup = country_name
            country = pycountry.countries.lookup(lookup)
            logger.debug(
                'pycountry:country:\n%s', pformat(country.__dict__['_fields'], indent=4))
        p = CampaPlace(
            pid=country.alpha_2, 
            types=['country', 'ADM1'],
            project_name=country_name,
            alternate_name=lookup,
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
        logger = self._get_logger()
        village = None
        try:
            village = self.districts[village_name]
        except KeyError:
            print(
                Fore.CYAN + Style.BRIGHT + 'WIKIDATA LOOKUP: "{}" ({})'
                ''.format(village_name, 'village') + Style.RESET_ALL)
            wikidata = suggest(village_name)
            logger.debug(pformat(wikidata, indent=4))
            if wikidata is not None:
                self.villages[village_name] = wikidata
                self._save_villages()
                village = wikidata
        else:
            logger.debug('using stored wikidata village information')
        logger.debug('wikidata:\n%s', pformat(village, indent=4))
        village_slug = '-'.join(
            re.sub(r'[()-_]+', '', norm(village_name).lower()).split())
        if village is not None:
            p = CampaPlace(
                pid=village_slug,
                types=['village', 'PPL'],
                project_name=village_name,
                **village
            )
        else:
            p = self._make_place(pid=village_slug, ptype='village', **kwargs)
        logger.debug('CampaPlace:\n%s', pformat(p.__dict__, indent=4))
        return p

    def _present(self, field_name, value):
        if value == '':
            logger = self._get_logger()
            logger.info('IGNORED: %s (%s)', field_name, 'empty string')
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

    def _save_villages(self):
        villages = Path(self.villages_path)
        villages.rename(self.villages_path + '.bak')
        villages = Path(self.villages_path)
        with villages.open('w', encoding='utf-8') as fp:
            json.dump(self.villages, fp, indent=4, ensure_ascii=False)
        del fp


def main(**kwargs):
    """
    main function
    """
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
    logger.info('Path to communes file: %s', str(dpath))
    villages = kwargs['villages']
    if villages == 'villages.json':
        vpath = Path(__file__).parent.parent / villages
    else:
        vpath = Path(villages).expanduser().resolve()
    logger.info('Path to villages file: %s', str(vpath))
    p = PlaceParser(dpath, cpath, vpath)
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

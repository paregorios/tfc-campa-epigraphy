#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse Campā Inventory row into places
"""

from campa.geography.place import CampaPlace
from campa.geography.logger import SelfLogger
from campa.geography.norm import norm
from colorama import Fore, Style
import inspect
import json
from pathlib import Path
from pprint import pformat
import pycountry
import re
import sys
from wikidata_suggest import suggest


class PlaceParser(SelfLogger):

    def __init__(self, districts, communes, villages, gazetteer):
        self.cache = {}
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
        self.gazetteer = gazetteer

    def parse(self, **kwargs):
        logger = self._get_logger()
        logger.debug('kwargs:\n%s', pformat(kwargs, indent=4))
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
            if place is not None:
                self.gazetteer.set_place(place)

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
            try:
                name = kwargs['project_name']
            except KeyError:
                name = kwargs['name']
            slug = '-'.join(
                re.sub(r'[()-_]+', '', norm(name).lower()).split())
            p = CampaPlace(pid=slug, types=types, gazetteer=self.gazetteer, **kwargs)
        else:
            p = CampaPlace(pid=pid, types=types, gazetteer=self.gazetteer, **kwargs)
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
            commune = self._suggest_wikidata(commune_name, 'commune')
            if commune is not None:
                self.communes[commune_name] = commune
                self._save_communes()
        else:
            logger.debug('using stored wikidata commune information')
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
        lookup = None
        if not self._present('country', country_name):
            return
        try:
            country = self.cache[country_name]
        except KeyError:
            if country_name == 'Cambodge':
                lookup = 'Cambodia'
            else:
                lookup = country_name
            country = self._suggest_pycountry(lookup, 'country')
            if country is None:
                raise NotImplementedError(country_name)
            else:
                self.cache[country_name] = country
        else:
            logger.debug('using stored pycountry country information')
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
            district = self._suggest_wikidata(district_name, 'district')
            if district is not None:
                self.districts[district_name] = district
                self._save_districts()
        else:
            logger.debug('using stored wikidata district information')
        if district is None:
            district = kwargs
        try:
            district['name']
        except KeyError:
            district['name'] = district_name
        else:
            district['project_name'] = district_name
        p = self._make_place(pid='slug', ptype='district', **district)
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
        province = None
        if not self._present('province', province_name):
            return
        try:
            province = self.cache[province_name]
        except KeyError:
            province = self._suggest_pycountry(province_name, 'province')
            if province is None:
                raise NotImplementedError(province_name)
            else:
                self.cache[province_name] = province
        else:
            logger.debug('using stored pycountry province information')
        if province is None:
            province = kwargs
        else:
            province = province.__dict__['_fields']
        try:
            province['name']
        except KeyError:
            province['name'] = province_name
        else:
            province['project_name'] = province_name
        p = self._make_place(pid='slug', ptype='province', **province)
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
            village = self._suggest_wikidata(village_name, 'village')
            if village is not None:
                self.villages[village_name] = village
                self._save_villages()
        else:
            logger.debug('using stored wikidata village information')
        if village is None:
            village = kwargs
        p = self._make_place(
            name=village_name, pid='slug', ptype='village', **village)
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

    def _suggest_pycountry(self, term, ptype):
        logger = self._get_logger()
        if ptype == 'country':
            suggestion = pycountry.countries.lookup(term)
        elif ptype == 'province':
            suggestion = pycountry.subdivisions.lookup(term)
        else:
            raise NotImplementedError(ptype, term)
        msg = (
            '{}:\n{}'
            ''.format(
                ptype,
                pformat(suggestion.__dict__['_fields'], indent=4)))
        logger.debug(msg)
        return suggestion

    def _suggest_wikidata(self, term, ptype):
        logger = self._get_logger()
        print(
            Fore.CYAN + Style.BRIGHT + 'WIKIDATA LOOKUP: "{}" ({})'
            ''.format(term, ptype) + Style.RESET_ALL)
        suggestion = suggest(term)
        if suggestion is not None:
            msg = (
                '{}:\n{}'
                ''.format(
                    ptype,
                    pformat(suggestion.__dict__['_fields'], indent=4)))
            logger.debug(msg)
        else:
            logger.debug('No wikidata suggestion was accepted by the user')
        return suggestion



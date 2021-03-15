#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert Campā inventory to geodata
"""

from airtight.cli import configure_commandline
from encoded_csv import get_csv
import logging
from pprint import pprint
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


class CampaPlace(object):

    def __init__():
        pass



def norm(raw):
    return normalize_unicode(normalize_space(raw))


def register(data, geod, index):
    register_country(data, geod, index)
    register_province(data, geod, index)


def register_country(data, geod, index):
    if data['country'] == '':
        logger.warning(
            (
                'IGNORED: No country for Campā Inscription Number {}'
                ''.format(data['cnumber'])))
        return
    term = data['country']
    country_id = get_country(term, index)
    try:
        geod[country_id]
    except KeyError:
        geod[country_id] = {
            'name': term,
            'id': country_id
        }
    indexit(term, country_id, index)


def get_country(raw_term, index):
    term = raw_term
    try:
        country_id = index[term]
    except KeyError:
        if term == 'Cambodge':
            term = 'Cambodia'
        elif term == 'Laos':
            term = "Lao People's Democratic Republic"
        these_countries = pycountry.countries.search_fuzzy(term)
        if len(these_countries) != 1:
            raise RuntimeError((raw_term, these_countries))
        country_id = these_countries[0].alpha_2
    return country_id


def handle_kompong_siem(term, geod, index):
    # https://en.wikipedia.org/wiki/Kampong_Siem_District
    province_id = 'KH-3'
    district_id = '{}:{}'.format(
        province_id, '-'.join(term.lower().split()))
    try:
        geod[province_id]
    except KeyError:
        geod[province_id] = {
            'name': 'Kampong Cham',
            'id': province_id,
            'country': 'KH',
            'types': ['province', 'ADM1', 'khaet']
        }
    indexit('Kampong Cham', province_id, index)
    try:
        geod[district_id]
    except KeyError:
        geod[district_id] = {
            'name': 'Kompong Siem',
            'id': district_id,
            'country': 'KH',
            'types': ['district', 'ADM2', 'srok']
        }
    indexit(term, district_id, index)


def get_province(data, geod, index):
    term = data['province']
    try:
        province_id = index[term]
    except KeyError:
        country_id = get_country(data['country'], index)
        try:
            province = pycountry.subdivisions.lookup(term)
        except LookupError:
            shred = '_'.join(term.lower().split())
            try:
                logger.debug('boop')
                province = getattr(
                    sys.modules[__name__],
                    'handle_{}'.format(shred))(
                        term, geod, index
                    )
            except AttributeError:
                raise RuntimeError('no handler')
        
            raise LookupError(
                (
                    'Failed lookup on "{}" in {} among {}'
                    ''.format(
                        term, data['country'],
                        [
                            s.name for s in pycountry.subdivisions.get(
                                country_code=country_id)]))
            )
        if province.country_code != country_id:
            raise RuntimeError((term, province))
    else:
        province = pycountry.subdivisions.get(code=province_id)
    return province

        
def register_province(data, geod, index):
    if data['province'] == '':
        logger.warning(
            (
                'IGNORED: No province for Campā Inscription Number {}'
                ''.format(data['cnumber'])))
        return   
    term = data['province']
    province = get_province(data, geod, index)
    province_id = province.code
    try:
        geod[province_id]
    except KeyError:
        geod[province_id] = {
            'name': term,
            'id': province_id,
            'country': province.country_code,
            'types': [province.type.lower(), 'ADM1', 'khaet']
        }
    indexit(term, province_id, index)
    
    
    

def indexit(term, target, index):
    try:
        index[term]
    except KeyError:
        index[term] = target
    else:
        if target != index[term]:
            raise RuntimeError((term, target, index[term]))



def main(**kwargs):
    """
    main function
    """
    logger = logging.getLogger(sys._getframe().f_code.co_name)
    data = get_csv(kwargs['infile'])
    logger.info(data['fieldnames'])
    logger.info('Rows in file: {}'.format(len(data['content'])))
    geod = {}
    index = {}
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
        register(clean_data, geod, index)
    pprint(geod, indent=4)
    pprint(index, indent=4)
            

if __name__ == "__main__":
    main(**configure_commandline(
        OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))

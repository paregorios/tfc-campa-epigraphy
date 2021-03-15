#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert Campā inventory to geodata
"""

from airtight.cli import configure_commandline
from encoded_csv import get_csv
from iso3166 import countries_by_name
import logging
from pprint import pprint
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


def register(data, geod, index):
    if data['country'] != '':
        register_country(data, geod, index)


def register_country(data, geod, index):
    key = data['country'].upper()
    if key == 'VIETNAM':
        key = 'VIET NAM'
    elif key == 'CAMBODGE':
        key = 'CAMBODIA'
    elif key == 'LAOS':
        key = "LAO PEOPLE'S DEMOCRATIC REPUBLIC"
    try:
        country_info = countries_by_name[key]
    except KeyError:
        for k in countries_by_name.keys():
            print(k)
        raise
    country_id = 'iso3166:{}'.format(country_info.alpha3)
    try:
        geod[country_id]
    except KeyError:
        geod[country_id] = {
            'name': country_info.name,
            'id': country_id
        }
    indexit(data['country'], country_id, index)


def indexit(term, target, index):
    try:
        index[term]
    except KeyError:
        index[term] = []
    if target not in index[term]:
        index[term].append(target)
    


def main(**kwargs):
    """
    main function
    """
    logger = logging.getLogger(sys._getframe().f_code.co_name)
    data = get_csv(kwargs['infile'])
    logger.debug(data['fieldnames'])
    logger.info('Rows in file: {}'.format(len(data['content'])))
    geod = {}
    index = {}
    for row in data['content']:
        # country -> province -> district -> commune -> village -> position
        clean_data = {
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

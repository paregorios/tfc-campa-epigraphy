#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert Campā inventory to geodata
"""

from airtight.cli import configure_commandline
from campa.geography.gazetteer import Gazetteer
from campa.geography.norm import norm
from campa.geography.parser import PlaceParser
from encoded_csv import get_csv
import logging
from logging import debug, info, warning, error, fatal
from pathlib import Path
from pprint import pformat, pprint
import re
import sys
from textnorm import normalize_space, normalize_unicode
from wikidata.client import Client as wdClient

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
        dpath = Path(__file__).parent.parent / 'data' / districts
    else:
        dpath = Path(districts).expanduser().resolve()
    logger.info('Path to districts file: %s', str(dpath))
    communes = kwargs['communes']
    if communes == 'communes.json':
        cpath = Path(__file__).parent.parent / 'data' / communes
    else:
        cpath = Path(communes).expanduser().resolve()
    logger.info('Path to communes file: %s', str(dpath))
    villages = kwargs['villages']
    if villages == 'villages.json':
        vpath = Path(__file__).parent.parent / 'data' / villages
    else:
        vpath = Path(villages).expanduser().resolve()
    logger.info('Path to villages file: %s', str(vpath))
    p = PlaceParser(dpath, cpath, vpath, g)
    for i, row in enumerate(data['content']):
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
        p.parse(**clean_data)
        if i == 20:
            g.dump()
            sys.exit()

if __name__ == "__main__":
    main(**configure_commandline(
        OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))

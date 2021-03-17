#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Normalization utilities
"""

from textnorm import normalize_space, normalize_unicode


def norm(raw):
    return normalize_unicode(normalize_space(raw))

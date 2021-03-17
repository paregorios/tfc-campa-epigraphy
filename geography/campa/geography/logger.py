#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Superclass for self-logging
"""

import logging
import sys


class SelfLogger(object):
    """
    Inherit from this class to get a method that returns a logger
    whose name includes the class name and the calling method name
    """

    def __init__(self):
        pass

    def _get_logger(self):
        """
        Get a logger named for the context class and calling method
        """
        name = ':'.join((
            self.__class__.__name__,
            sys._getframe().f_back.f_code.co_name))
        return logging.getLogger(name)
        
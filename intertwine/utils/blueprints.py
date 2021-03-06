#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from flask import Blueprint


class SingletonBlueprint(Blueprint):
    '''Wraps a Blueprint with a singleton approach'''
    singleton_registry = {}

    def __new__(cls, *args, **kwds):
        key = (args, tuple((k, v) for k, v in sorted(kwds.items())))
        instance = cls.singleton_registry.get(key) or Blueprint(*args, **kwds)
        cls.singleton_registry[key] = instance
        return instance


def create_singleton_blueprint(import_name=None, name=None, *args, **kwds):

    return SingletonBlueprint(import_name, name, *args, **kwds)

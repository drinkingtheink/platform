#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''Loads geo data into Intertwine'''
from config import DevConfig
from data.data_process import DataSessionManager
from data.geos.models import (BaseGeoDataModel, State, CBSA, County, Place,
                              LSAD, GHR, F02)
from intertwine.utils import Trackable
from intertwine.geos.models import BaseGeoModel, Geo


def load_geo_data():

    # Session for geo.db, which contains the geo source data
    geo_dsm = DataSessionManager(db_config=DevConfig.GEO_DATABASE,
                                 ModelBases=[BaseGeoDataModel])
    geo_session = geo_dsm.session

    # Session for main Intertwine db, where geo data is loaded
    dsm = DataSessionManager(db_config=DevConfig.DATABASE,
                             ModelBases=[BaseGeoModel])
    session = dsm.session

    Trackable.register_existing(session, Geo)
    Trackable.clear_updates()

    us = Geo(name='United States', abbrev='US', the_prefix=True,
             geo_type='country', descriptor='federal republic')

    # State-level aggregation including PR, but excluding DC
    ghrs = geo_session.query(GHR).filter(GHR.sumlev == '040',
                                         GHR.geocomp == '00',
                                         GHR.statefp != '11').all()
    for ghr in ghrs:
        Geo(name=ghr.state.name,
            abbrev=ghr.state.stusps,
            path_parent=us,
            geo_type='subdivision1',
            descriptor='state',
            parents=[us],
            total_pop=ghr.f02.p0020001,
            urban_pop=ghr.f02.p0020002)
    Geo['us/pr'].descriptor = 'territory'

    more_areas = geo_session.query(State).filter(State.stusps.in_(['AS', 'GU', 'MP', 'UM', 'VI'])).all()
    for area in more_areas:
        Geo(name=area.name,
            abbrev=area.stusps,
            path_parent=us,
            geo_type='subdivision1',
            descriptor='territory',
            parents=[us])

    # CSAs

    # CBSAs

    # Counties

    # Places

    return Trackable.catalog_updates()

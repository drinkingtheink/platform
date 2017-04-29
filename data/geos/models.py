#!/usr/bin/env python
# -*- coding: utf-8 -*-
from collections import OrderedDict, namedtuple

from alchy.model import ModelBase, make_declarative_base
from sqlalchemy import (orm, types, Column, ForeignKey, Index,
                        PrimaryKeyConstraint, ForeignKeyConstraint)

from intertwine.utils.mixins import AutoTablenameMixin

BaseGeoDataModel = make_declarative_base(Base=ModelBase)


class State(BaseGeoDataModel, AutoTablenameMixin):
    statefp = Column(types.String(2), primary_key=True)  # 48
    stusps = Column(types.String(2), unique=True)        # TX
    name = Column(types.String(60), unique=True)         # Texas
    statens = Column(types.String(8), unique=True)       # 01779801
    _map_by_fips = None

    @classmethod
    def get_map_by_fips(cls):
        if not cls._map_by_fips:
            cls._create_map_by_fips()
        return cls._map_by_fips

    @classmethod
    def _create_map_by_fips(cls):
        states = cls.query.order_by(cls.statefp)
        cls._map_by_fips = OrderedDict(
            (state.statefp, state) for state in states)

    @classmethod
    def get_map_by_abbrev(cls):
        if not cls._map_by_abbrev:
            cls._create_map_by_abbrev()
        return cls._map_by_abbrev

    @classmethod
    def _create_map_by_abbrev(cls):
        states = cls.query.order_by(cls.stusps)
        cls._map_by_abbrev = OrderedDict(
            (state.stusps, state) for state in states)

    @classmethod
    def get_map_by_name(cls):
        if not cls._map_by_name:
            cls._create_map_by_name()
        return cls._map_by_name

    @classmethod
    def _create_map_by_name(cls):
        states = cls.query.order_by(cls.name)
        cls._map_by_name = OrderedDict(
            (state.name, state) for state in states)


class CBSA(BaseGeoDataModel, AutoTablenameMixin):
    '''Core Based Statistical Area (CBSA)'''
    cbsa_code = Column(types.String(5))                 # 12420
    metro_division_code = Column(types.String(5))
    csa_code = Column(types.String(3))
    cbsa_name = Column(types.String(60))                # Austin-Round Rock, TX
    cbsa_type = Column(types.String(30))                # Metro...(vs Micro...)
    metro_division_name = Column(types.String(60))
    csa_name = Column(types.String(60))
    county_name = Column(types.String(60))              # Travis County
    state_name = Column(types.String(60))               # Texas
    statefp = Column(types.String(2), ForeignKey('state.statefp'))  # 48
    state = orm.relationship('State', viewonly=True)

    countyfp = Column(types.String(3))                  # 453
    county_type = Column(types.String(30))              # Central (vs Outlying)

    countyid = Column(types.String(5), ForeignKey('county.geoid'),
                      primary_key=True)
    county = orm.relationship('County', uselist=False, back_populates='cbsa')


class County(BaseGeoDataModel, AutoTablenameMixin):
    stusps = Column(types.String(2),                    # TX
                    ForeignKey('state.stusps'))
    state = orm.relationship('State')
    geoid = Column(types.String(5), primary_key=True)   # 48453
    cbsa = orm.relationship('CBSA', uselist=False, back_populates='county')

    ansicode = Column(types.String(8), unique=True)     # 01384012
    name = Column(types.String(60))                     # Travis County
    pop10 = Column(types.Integer)                       # 1024266
    hu10 = Column(types.Integer)                        # 441240
    aland = Column(types.Integer)                       # 2564612388
    awater = Column(types.Integer)                      # 84967219
    aland_sqmi = Column(types.Float)                    # 990.202
    awater_sqmi = Column(types.Float)                   # 32.806
    intptlat = Column(types.Float)                      # 30.239513
    intptlong = Column(types.Float)                     # -97.69127


class Cousub(BaseGeoDataModel, AutoTablenameMixin):
    stusps = Column(types.String(2),                    # MA
                    ForeignKey('state.stusps'))
    state = orm.relationship('State')
    geoid = Column(types.String(10), primary_key=True)  # 2502178690
    ansicode = Column(types.String(8), unique=True)     # 00618333
    name = Column(types.String(60))                     # Westwood town
    funcstat = Column(types.String(1))                  # A
    pop10 = Column(types.Integer)                       # 14618
    hu10 = Column(types.Integer)                        # 5431
    aland = Column(types.Integer)                       # 28182837
    awater = Column(types.Integer)                      # 740388
    aland_sqmi = Column(types.Float)                    # 10.881
    awater_sqmi = Column(types.Float)                   # 0.286
    intptlat = Column(types.Float)                      # 42.219645
    intptlong = Column(types.Float)                     # -71.216769


class Place(BaseGeoDataModel, AutoTablenameMixin):
    stusps = Column(types.String(2),                    # TX
                    ForeignKey('state.stusps'))
    state = orm.relationship('State')
    geoid = Column(types.String(7), primary_key=True)   # 4805000
    ansicode = Column(types.String(8), unique=True)     # 02409761
    name = Column(types.String(60))                     # Austin city
    lsad_code = Column(types.String(2),
                       ForeignKey('lsad.lsad_code'))    # 25
    lsad = orm.relationship('LSAD')
    funcstat = Column(types.String(1))                  # A
    pop10 = Column(types.Integer)                       # 790390
    hu10 = Column(types.Integer)                        # 354241
    aland = Column(types.Integer)                       # 771546901
    awater = Column(types.Integer)                      # 18560605
    aland_sqmi = Column(types.Float)                    # 297.896
    awater_sqmi = Column(types.Float)                   # 7.166
    intptlat = Column(types.Float)                      # 30.307182
    intptlong = Column(types.Float)                     # -97.755996


class LSAD(BaseGeoDataModel, AutoTablenameMixin):
    PREFIX = 'prefix'
    SUFFIX = 'suffix'
    AFFIXES = {PREFIX, SUFFIX}

    ACTUAL_TEXT = 'actual text'
    ANNOTATIONS = ['({})'.format(a) for a in (ACTUAL_TEXT, PREFIX, SUFFIX)]

    LSADMapRecord = namedtuple(
        'LSADMapRecord',
        ('lsad_code', 'description', 'geo_entity_type', 'display', 'affix'))
    _lsad_map = None

    lsad_code = Column(types.String(2), primary_key=True)  # 25
    description = Column(types.String(60))              # 'city (suffix)'
    geo_entity_type = Column(types.String(600))         # 'Consolidated City,
    # County or Equivalent Feature, County Subdivision, Economic Census Place,
    # Incorporated Place'

    @classmethod
    def get_map(cls):
        if not cls._lsad_map:
            cls._create_map()
        return cls._lsad_map

    @classmethod
    def _create_map(cls):
        lsads = cls.query.order_by(cls.lsad_code)
        cls._lsad_map = OrderedDict(
            (lsad.lsad_code, cls.LSADMapRecord(
                lsad_code=lsad.lsad_code,
                description=lsad.description,
                geo_entity_type=lsad.geo_entity_type,
                display=cls.deannotate(lsad.description),
                affix=(cls.PREFIX if (cls.PREFIX in lsad.description) else
                       cls.SUFFIX if (cls.SUFFIX in lsad.description) else
                       None)
                )) for lsad in lsads)

    @classmethod
    def deannotate(cls, text):
        for annotation in cls.ANNOTATIONS:
            text = text.split(' ' + annotation)[0]
        return text

    @classmethod
    def deaffix(cls, affixed_name, lsad_code):
        lsad_record = cls.get_map()[lsad_code]
        lsad, affix = lsad_record.display, lsad_record.affix

        if affix is None:
            return affixed_name, lsad

        lsad_tag_len = len(lsad) + 1

        if affix == cls.SUFFIX:
            lsad_tag = ' ' + lsad
            name = affixed_name[:-lsad_tag_len]
            removed_value = affixed_name[-lsad_tag_len:]

        elif affix == cls.PREFIX:
            lsad_tag = lsad + ' '
            name = affixed_name[lsad_tag_len:]
            removed_value = affixed_name[:lsad_tag_len]

        else:
            raise ValueError("Affix '{affix}' must be in {affixes}"
                             .format(affix=affix, affixes=cls.AFFIXES))

        if removed_value != lsad_tag:
            raise ValueError(
                "'{lsad_tag}' not found as {affix} of '{name}'"
                .format(lsad_tag=lsad_tag, affix=affix, name=affixed_name))

        return name, lsad


class Geoclass(BaseGeoDataModel, AutoTablenameMixin):
    # renamed from classfp
    geoclassfp = Column(types.String(2), primary_key=True)  # C1
    category = Column(types.String(60))                 # Incorporated Place
    name = Column(types.String(60))                     # Incorporated Place
    description = Column(types.String(300))             # An active
    # incorporated place that does not serve as a county subdivision equivalent


class GHRP(BaseGeoDataModel):
    '''
    Geographic Header Row Plus (GHRP)

    Contains all columns from the Geographic Header Row (GHR) plus:
    county_id, the concatenation of statefp and countyfp
    cousub_id, the concatenation of statefp, countyfp, and cousubfp
    place_id, the concatenation of statefp and placefp
    all columns from File 02.
    '''
    __tablename__ = 'ghrp'

    # RECORD CODES
    fileid = Column(types.String(6))
    stusab = Column(types.String(2))
    sumlev = Column(types.String(3))
    geocomp = Column(types.String(2))
    chariter = Column(types.String(3))
    cifsn = Column(types.String(2))
    logrecno = Column(types.Integer, primary_key=True)  # Changed to Integer
    # f02 = orm.relationship('F02', back_populates='ghrp', uselist=False)

    # GEOGRAPHIC AREA CODES
    region = Column(types.String(1))
    division = Column(types.String(1))

    # Renamed from state
    statefp = Column(types.String(2), ForeignKey('state.statefp'))
    state = orm.relationship('State', viewonly=True)

    # Renamed from county
    countyfp = Column(types.String(3))
    countycc = Column(types.String(2), ForeignKey('geoclass.geoclassfp'))
    countyclass = orm.relationship('Geoclass', foreign_keys='GHRP.countycc')
    countysc = Column(types.String(2))

    # Renamed from cousub
    cousubfp = Column(types.String(5))
    cousubcc = Column(types.String(2), ForeignKey('geoclass.geoclassfp'))
    cousubclass = orm.relationship('Geoclass', foreign_keys='GHRP.cousubcc')
    cousubsc = Column(types.String(2))

    # Renamed from place
    placefp = Column(types.String(5))
    placecc = Column(types.String(2), ForeignKey('geoclass.geoclassfp'))
    placeclass = orm.relationship('Geoclass', foreign_keys='GHRP.placecc')
    placesc = Column(types.String(2))

    tract = Column(types.String(6))
    blkgrp = Column(types.String(1))
    block = Column(types.String(4))
    iuc = Column(types.String(2))
    concit = Column(types.String(5))
    concitcc = Column(types.String(2))
    concitsc = Column(types.String(2))
    aianhh = Column(types.String(4))
    aianhhfp = Column(types.String(5))
    aianhhcc = Column(types.String(2))
    aihhtli = Column(types.String(1))
    aitsce = Column(types.String(3))
    aits = Column(types.String(5))
    aitscc = Column(types.String(2))
    ttract = Column(types.String(6))
    tblkgrp = Column(types.String(1))
    anrc = Column(types.String(5))
    anrccc = Column(types.String(2))
    cbsa = Column(types.String(5))
    cbsasc = Column(types.String(2))
    metdiv = Column(types.String(5))
    csa = Column(types.String(3))
    necta = Column(types.String(5))
    nectasc = Column(types.String(2))
    nectadiv = Column(types.String(5))
    cnecta = Column(types.String(3))
    cbsapci = Column(types.String(1))
    nectapci = Column(types.String(1))
    ua = Column(types.String(5))
    uasc = Column(types.String(2))
    uatype = Column(types.String(1))
    ur = Column(types.String(1))
    cd = Column(types.String(2))
    sldu = Column(types.String(3))
    sldl = Column(types.String(3))
    vtd = Column(types.String(6))
    vtdi = Column(types.String(1))
    reserve2 = Column(types.String(3))
    zcta5 = Column(types.String(5))
    submcd = Column(types.String(5))
    submcdcc = Column(types.String(2))
    sdelm = Column(types.String(5))
    sdsec = Column(types.String(5))
    sduni = Column(types.String(5))

    # AREA CHARACTERISTICS
    arealand = Column(types.Integer)  # in sq. meters
    areawatr = Column(types.Integer)  # in sq. meters
    name = Column(types.String(90))
    funcstat = Column(types.String(1))
    gcuni = Column(types.String(1))
    pop100 = Column(types.Integer)
    hu100 = Column(types.Integer)
    intptlat = Column(types.Float)
    intptlon = Column(types.Float)
    lsadc = Column(types.String(2), ForeignKey('lsad.lsad_code'))
    lsad = orm.relationship('LSAD')

    partflag = Column(types.String(1))

    # SPECIAL AREA CODES
    reserve3 = Column(types.String(6))
    uga = Column(types.String(5))
    statens = Column(types.String(8))
    countyns = Column(types.String(8))
    cousubns = Column(types.String(8))
    placens = Column(types.String(8))
    concitns = Column(types.String(8))
    aianhhns = Column(types.String(8))
    aitsns = Column(types.String(8))
    anrcns = Column(types.String(8))
    submcdns = Column(types.String(8))
    cd113 = Column(types.String(2))
    cd114 = Column(types.String(2))
    cd115 = Column(types.String(2))
    sldu2 = Column(types.String(3))
    sldu3 = Column(types.String(3))
    sldu4 = Column(types.String(3))
    sldl2 = Column(types.String(3))
    sldl3 = Column(types.String(3))
    sldl4 = Column(types.String(3))
    aianhhsc = Column(types.String(2))
    csasc = Column(types.String(2))
    cnectasc = Column(types.String(2))
    memi = Column(types.String(1))
    nmemi = Column(types.String(1))
    puma = Column(types.String(5))
    reserved = Column(types.String(18))

    # Added - concatenation of statefp and countyfp
    countyid = Column(types.String(5), ForeignKey('county.geoid'))
    county = orm.relationship('County')

    # Added - concatenation of statefp, countyfp, and cousubfp
    cousubid = Column(types.String(10), ForeignKey('cousub.geoid'))
    cousub = orm.relationship('Cousub')

    # Added - concatenation of statefp and placefp
    placeid = Column(types.String(7), ForeignKey('place.geoid'))
    place = orm.relationship('Place')

    # Added File 02 columns:
    p0020001 = Column(types.Integer)
    p0020002 = Column(types.Integer)
    p0020003 = Column(types.Integer)
    p0020004 = Column(types.Integer)
    p0020005 = Column(types.Integer)
    p0020006 = Column(types.Integer)

    __table_args__ = (
        Index('ix_ghrp',
              # ix for index
              'sumlev',
              'geocomp'),
        {}
        )


# class F02(BaseGeoDataModel):
#     __tablename__ = 'f02'
#     fileid = Column(types.String(6))
#     stusab = Column(types.String(2))
#     chariter = Column(types.String(3))
#     cifsn = Column(types.String(2))
#     logrecno = Column(types.Integer,
#                       ForeignKey('ghrp.logrecno'),
#                       primary_key=True)
#     ghrp = orm.relationship('GHRP', back_populates='f02')

#     p0020001 = Column(types.Integer)
#     p0020002 = Column(types.Integer)
#     p0020003 = Column(types.Integer)
#     p0020004 = Column(types.Integer)
#     p0020005 = Column(types.Integer)
#     p0020006 = Column(types.Integer)

#     __table_args__ = (
#         Index('ix_f02',
#               # ix for index
#               'logrecno'),
#         )

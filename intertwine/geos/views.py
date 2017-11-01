# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from operator import attrgetter

import flask
from flask import abort, jsonify, redirect, render_template, request

from . import blueprint
from .models import Geo, GeoLevel
from intertwine.utils.jsonable import Jsonable


@blueprint.route('/', methods=['GET'])
def render():
    '''Generic page rendering for top level'''
    geos = Geo.query.filter(Geo.path_parent is None,
                            ~Geo.alias_targets.any()).order_by(Geo.name).all()
    # glvls = GeoLevel.query.filter(GeoLevel.level == 'country').all()
    # geos = [glvl.geo for glvl in glvls]
    if len(geos) == 1:
        geo = geos[0]
        glvl = geo.levels.keys()[0]
        dlvl = GeoLevel.DOWN[glvl][0]

        by_name = sorted(geo.children.all(), key=attrgetter('name'))
        by_designation = sorted(by_name,
                                key=lambda g: g.levels[dlvl].designation)

        geos += by_designation
    template = render_template(
        'geos.html',
        current_app=flask.current_app,
        title="Geos",
        geos=geos)
    return template


@blueprint.route('/<path:geo_human_id>', methods=['GET'])
def render_geo(geo_human_id):
    '''Geo Page'''
    human_id = geo_human_id.lower()
    geo = Geo.query.filter_by(human_id=human_id).first()

    if geo is None:
        # TODO: Instead of aborting, reroute to geo_not_found page
        # Oops! 'X' is not a geo found in Intertwine.
        # Did you mean:
        # <geo_1>
        # <geo_2>
        # <geo_3>
        abort(404)

    alias_targets = geo.alias_targets
    if alias_targets:
        target = alias_targets[0].human_id
        return redirect('/geos/{}'.format(target), code=302)
    # Austin, Texas, United States
    title = geo.display()

    geo = geo

    # get list of top problems in geo based on followers, activity, trending
    # top_problems =

    template = render_template(
        'geo.html',
        current_app=flask.current_app,
        title=title,
        geo=geo,
        # top_problems=top_problems,
    )
    return template


@blueprint.route('/', methods=['POST'])
def match_geos():
    '''
    Find geos endpoint

    Usage:
    curl -H "Content-Type: application/json" -X POST -d '{
        "match_string": "austin, tx", "match_limit": -1
    }' 'http://localhost:5000/geos/'
    '''
    payload = request.get_json()
    match_string = payload.get('match_string')
    match_limit = payload.get('match_limit')
    geo_kwargs = dict(hide={Geo.PARENTS, Geo.CHILDREN, Geo.PATH_CHILDREN},
                      limit=-1)
    json_kwarg_map = {Geo: geo_kwargs}
    if match_limit:
        json_kwarg_map[object] = dict(limit=match_limit)
    geo_matches = Geo.find_matches(match_string)
    return jsonify(Jsonable.jsonify_value(geo_matches, json_kwarg_map))

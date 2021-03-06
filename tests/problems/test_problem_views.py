#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pytest
import sys

from intertwine.problems.models import ProblemConnection as PC
from intertwine.problems.models import AggregateProblemConnectionRating as APCR

# Python version compatibilities
U_LITERAL = 'u' if sys.version_info < (3,) else ''


@pytest.mark.unit
@pytest.mark.smoke
@pytest.mark.parametrize("connection_category, is_real_community", [
    (connection_category, is_real_community)
    for connection_category in PC.CATEGORY_MAP
    for is_real_community in (True, False)])
def test_add_rated_problem_connection(session, client, connection_category,
                                      is_real_community):
    '''Tests aggregate problem connection rating model interaction'''
    import json

    from intertwine.communities.models import Community
    from intertwine.geos.models import Geo
    from intertwine.problems.models import Problem, ProblemConnection
    from intertwine.utils.tools import vardygrify

    problem_name_base = 'Test Problem'
    problem1 = Problem(problem_name_base + ' 01')
    org = 'University of Texas'
    geo = Geo('Austin')
    session.add(problem1)
    session.add(geo)

    if is_real_community:
        community = Community(problem=problem1, org=org, geo=geo)
        session.add(community)
    else:
        community = vardygrify(Community, problem=problem1, org=org, geo=geo)

    session.commit()

    axis = (PC.CAUSAL if connection_category in {PC.DRIVERS, PC.IMPACTS}
            else PC.SCOPED)
    problem2_name = problem_name_base + ' 02'
    problem_a_name, problem_b_name = (
        (problem1.name, problem2_name)
        if connection_category in {PC.IMPACTS, PC.NARROWER}
        else (problem2_name, problem1.name))

    aggregation = APCR.STRICT

    request_payload = {
        'connection': {
            'axis': axis,
            'problem_a': problem_a_name,
            'problem_b': problem_b_name
        },
        'community': {
            'problem': problem1.human_id,
            'org': org,
            'geo': geo.human_id
        },
        'aggregation': aggregation
    }

    request_data = json.dumps(request_payload)
    url = 'http://localhost:5000/problems/rated_connections'

    response = client.post(url, data=request_data,
                           content_type='application/json')

    assert response is not None

    problem2 = Problem[Problem.create_key(name=problem2_name)]
    assert problem2 is not None

    response_data = response.get_data(as_text=True)
    response_payload = json.loads(response_data)
    root = response_payload['root']
    rated_connection = response_payload[root]

    assert rated_connection['adjacent_problem_name'] == problem2_name
    assert rated_connection['aggregation'] == APCR.STRICT

    assert rated_connection['community'] == community.json_key()

    problem_a_human_id = Problem.convert_name_to_human_id(problem_a_name)
    problem_a = Problem[problem_a_human_id]
    problem_b_human_id = Problem.convert_name_to_human_id(problem_b_name)
    problem_b = Problem[problem_b_human_id]
    problem_connection = ProblemConnection[ProblemConnection.create_key(
        axis, problem_a, problem_b)]
    assert rated_connection['connection'] == problem_connection.json_key()

    assert rated_connection['connection_category'] == connection_category

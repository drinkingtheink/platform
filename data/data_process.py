#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''Decodes data

Usage:
    data_process.py [options] <json_path>

Options:
    -h --help       This message
    -v --verbose    More information
    -q --quiet      Less information
'''
from __future__ import print_function

import json
import logging
import os
import os.path
import sys

from intertwine.problems.models import Problem, ProblemConnection, ProblemConnectionRating
from intertwine.problems.exceptions import InvalidJSONPath


def decode_problems(json_data):
    '''Returns entities created from problem json_data

    Takes as input a list of json data loads, each from a separate JSON
    file and returns a dictionary where the keys are classes and the
    values are corresponding sets of objects updated from the JSON
    file(s).

    Resets the tracking of updates via the Trackable metaclass for
    problems, connections, and ratings each time it is called.
    '''
    Problem._updates = set()
    ProblemConnection._updates = set()
    ProblemConnectionRating._updates = set()

    for json_data_load in json_data:
        for data_key, data_value in json_data_load.items():
            Problem(name=data_key, **data_value)

    updates = {
        'Problem': Problem._updates,
        'ProblemConnection': ProblemConnection._updates,
        'ProblemConnectionRating': ProblemConnectionRating._updates,
    }
    return updates


def decode(json_path, *args, **options):
    '''Loads JSON files within a path and returns data structures

    Given a path to a JSON file or a directory containing JSON files,
    returns a dictionary where the keys are classes and the values are
    corresponding sets of objects updated from the JSON file(s).

    Calls another function to actually decode the json_data. This
    other function's name begins with 'decode_' and ends with the last
    directory in the absolute json_path: decode_<dir_name>(json_data)

    Usage:
    >>> json_path = '/data/problems/problems00.json'  # load a JSON file
    >>> u0 = decode(json_path)  # get updates from data load
    >>> json_path = '/data/problems/'  # load all JSON files in a directory
    >>> u1 = decode(json_path)  # get updates from next data load
    >>> u1_problems = u1['Problem']  # get set of updated problems
    >>> u1_connections = u1['ProblemConnection']  # set of updated connections
    >>> u1_ratings = u1['ProblemConnectionRating']  # set of updated ratings
    >>> p0 = Problem('poverty')  # get existing 'Poverty' problem
    >>> p1 = Problem('homelessness')  # get existing 'Homelessness' problem
    >>> p2 = Problem['domestic_violence']  # Problem is subscriptable
    >>> for k in Problem:  # Problem is iterable
    ...    print(Problem[k])
    '''
    # Gather valid json_paths based on the given file or directory
    json_paths = []
    if os.path.isfile(json_path):
        if (json_path.rsplit('.', 1)[-1].lower() == 'json' and
                'schema' not in os.path.basename(json_path).lower()):
            json_paths.append(json_path)
    elif os.path.isdir(json_path):
        json_paths = [os.path.join(json_path, f) for f in os.listdir(json_path)
                      if (os.path.isfile(os.path.join(json_path, f)) and
                          f.rsplit('.', 1)[-1].lower() == 'json' and
                          'schema' not in f.lower())]
    if len(json_paths) == 0:
        raise InvalidJSONPath(path=json_path)

    # Load raw json_data from each of the json_paths
    json_data = []
    for path in json_paths:
        with open(path) as json_file:
            # TODO: May need to change this to load incrementally in the future
            json_data.append(json.load(json_file))

    # Determine the decode function based on directory name and then call it
    if os.path.isfile(json_path):
        dir_name = os.path.abspath(json_path).rsplit('/', 2)[-2]
    else:
        dir_name = os.path.abspath(json_path).rsplit('/', 1)[-1]
    function_name = 'decode_' + dir_name
    module = sys.modules[__name__]
    decode_function = getattr(module, function_name)
    return decode_function(json_data)


if __name__ == '__main__':
    from docopt import docopt

    def fix(option):
        option = option.lstrip('--')
        option = option.lstrip('<').rstrip('>')
        option = option.replace('-', '_')
        return option

    options = {fix(k): v for k, v in docopt(__doc__).items()}
    if options.get('verbose'):
        logging.basicConfig(level=logging.DEBUG)
    elif options.get('quiet'):
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.basicConfig(level=logging.INFO)

    decode(**options)

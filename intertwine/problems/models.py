#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import re
from collections import OrderedDict, namedtuple
from numbers import Real
from operator import attrgetter

from past.builtins import basestring
from sqlalchemy import Column, ForeignKey, Index, or_, orm, types
from titlecase import titlecase

from intertwine import IntertwineModel
from intertwine.geos.models import Geo
from intertwine.third_party import urlnorm
from intertwine.utils.enums import UriType

from .exceptions import (CircularConnection,
                         InconsistentArguments,
                         InvalidAggregateConnectionRating, InvalidAggregation,
                         InvalidConnectionAxis, InvalidEntity,
                         InvalidProblemConnectionRating,
                         InvalidProblemConnectionWeight,
                         InvalidProblemForConnection, InvalidUser)

BaseProblemModel = IntertwineModel


class Image(BaseProblemModel):
    '''Base class for images'''
    SUB_BLUEPRINT = 'images'
    URI_TYPE = UriType.PRIMARY

    # TODO: make Image work with any entity (not just problems), where
    # each image can be attached to multiple entities
    problem_id = Column(types.Integer, ForeignKey('problem.id'))
    problem = orm.relationship('Problem', back_populates='images')
    url = Column(types.String(2048))

    # TODO: add following:
    #
    # attribution:
    # title         # title of the work
    # author        # name or username (on source site) who owns the material
    # org           # organization that owns the material
    # source        # same as url? consider renaming url as source?
    # license       # name of license; mapped to license_url
    #               # acceptable licenses on Intertwine:
    #               # NONE:      PUBLIC DOMAIN
    #               # CC BY:     ATTRIBUTION
    #               # CC BY-SA:  ATTRIBUTION-SHAREALIKE
    #               # CC BY-ND:  ATTRIBUTION-NODERIVS
    #               # foter.com/blog/how-to-attribute-creative-commons-photos/
    #
    # users:
    # authored_by   # user who is author
    # added_by      # user who added
    # modified_by   # users who modified
    #
    # ratings       # common Base for ContentRating & ProblemConnectionRating?
    #
    # image-specific:
    # caption       # additional text beyond title
    # date          # date original was made
    # location      # where the photo was captured, if applicable
    # file          # local copy of image
    # dimensions    # in pixels

    Key = namedtuple('ImageKey', 'problem, url')

    @classmethod
    def create_key(cls, problem, url, **kwds):
        '''
        Create key for an image

        Return a key allowing the Trackable metaclass to register an
        image. The key is a namedtuple of problem and url.
        '''
        return cls.Key(problem, urlnorm.norm(url))

    def derive_key(self, **kwds):
        '''
        Derive key from an image instance

        Return the registry key used by the Trackable metaclass from an
        image instance. The key is a namedtuple of problem and url.
        '''
        return self.__class__.Key(self.problem, self.url)

    def __init__(self, url, problem):
        '''
        Initialize a new image from a url

        Inputs are key-value pairs based on the JSON problem schema.
        '''
        self.url = urlnorm.norm(url)
        self.problem = problem


class AggregateProblemConnectionRating(BaseProblemModel):
    '''
    Base class for aggregate problem connection ratings

    Rating aggregations are used to display connections on the problem
    network and this class enables caching so they do not need to be
    recalculated on each request. Ratings are aggregated across users
    within a community context of problem, org, and geo.

    Currently, aggregations are only created when the problem network is
    first rendered within a given community. The cumulative weight
    across all the ratings aggregated is also stored, allowing the
    aggregate rating to be updated without having to recalculate the
    aggregation across all the included ratings.

    I/O:
    community: Community context for the aggregate rating
    connection: Connection being rated
    aggregation='strict': String specifying the aggregation method:
        - 'strict': include only ratings in the associated community
        - 'inclusive': include all ratings within sub-orgs/geos
        - 'inherited': include ratings from a different community
    rating=None: Real number between 0 and 4 inclusive; rating and
        weight must both be defined or both be None
    weight=None: Real number greater than or equal to 0 that
        reflects the cumulative weight of all aggregated ratings
    ratings=None: Iterable of ProblemConnectionRating specifying the
        set of ratings to be aggregated. Ratings and rating/weight
        cannot both be specified.
    '''
    SUB_BLUEPRINT = 'rated_connections'
    STRICT = 'strict'
    AGGREGATIONS = {STRICT}

    NO_RATING = -1
    NO_WEIGHT = 0

    MIN_RATING = 0
    MAX_RATING = 4
    MIN_WEIGHT = 0
    MAX_WEIGHT = 10 ** 10

    community_id = Column(types.Integer, ForeignKey('community.id'))
    community = orm.relationship('Community',
                                 back_populates='aggregate_ratings')

    connection_id = Column(types.Integer, ForeignKey('problem_connection.id'))
    connection = orm.relationship('ProblemConnection',
                                  back_populates='aggregate_ratings')

    connection_category = Column(types.String(16))
    aggregation = Column(types.String(16))
    rating = Column(types.Float)
    weight = Column(types.Float)

    __table_args__ = (
        Index('ux_aggregate_problem_connection_rating',
              # ux for unique index
              'community_id',
              'aggregation',
              'connection_id',
              unique=True),
        Index('ix_aggregate_problem_connection_rating:by_category',
              # ix for index
              'community_id',
              'aggregation',
              'connection_category'),)

    Key = namedtuple('AggregateProblemConnectionRatingKey',
                     'connection, community, aggregation')

    @property
    def adjacent_problem_name(self):
        problem = self.community.problem
        connection = self.connection
        problem_a, problem_b = connection.problems
        adjacent_problem = (problem_a if problem is problem_b else problem_b)
        return adjacent_problem.name

    @property
    def adjacent_community_url(self):
        from ..communities.models import Community
        problem = self.community.problem
        connection = self.connection
        problem_a, problem_b = connection.problems
        adjacent_problem = (problem_a if problem is problem_b else problem_b)
        return Community.form_uri(Community.Key(
            adjacent_problem, self.community.org, self.community.geo))

    @classmethod
    def create_key(cls, connection, community, aggregation=STRICT, **kwds):
        '''
        Create key for an aggregate rating

        Return a key allowing the Trackable metaclass to register an
        aggregate problem connection rating instance. The key is a
        namedtuple of connection, community, and aggregation.
        '''
        return cls.Key(connection, community, aggregation)

    def derive_key(self, **kwds):
        '''
        Derive key from an aggregate rating instance

        Return the registry key used by the Trackable metaclass from an
        aggregate problem connection rating instance. The key is a
        namedtuple of connection, community, and aggregation fields.
        '''
        return self.__class__.Key(
            self.connection, self.community, self.aggregation)

    @classmethod
    def calculate_values(cls, ratings):
        '''
        Calculate values

        Given an iterable of ratings, returns a tuple consisting of the
        aggregate rating and the aggregate weight. If ratings is empty,
        the aggregate rating defaults to -1 and the aggregate weight
        defaults to 0.
        '''
        weighted_rating_total = aggregate_weight = cls.NO_WEIGHT
        for r in ratings:
            weighted_rating_total += r.rating * r.weight
            # Sub w/ r.user.expertise(problem, org, geo)
            aggregate_weight += r.weight

        aggregate_rating = ((weighted_rating_total * 1.0 / aggregate_weight)
                            if aggregate_weight > cls.NO_WEIGHT
                            else cls.NO_RATING)

        return (aggregate_rating, aggregate_weight)

    def update_values(self, new_user_rating, new_user_weight,
                      old_user_rating=None, old_user_weight=None):
        '''Update values'''
        old_user_rating = 0 if old_user_rating is None else old_user_rating
        old_user_weight = 0 if old_user_weight is None else old_user_weight

        increase = new_user_rating * new_user_weight
        decrease = old_user_rating * old_user_weight

        new_aggregate_weight = (
            self.weight + new_user_weight - old_user_weight)
        new_aggregate_rating = (
            (self.rating * self.weight + increase - decrease) * 1.0 /
            new_aggregate_weight)

        self.rating, self.weight = new_aggregate_rating, new_aggregate_weight

    def __init__(self, connection, community, aggregation=STRICT,
                 rating=None, weight=None, ratings=None):
        problem, org, geo = community.derive_key()
        self.connection_category = connection.derive_category(problem)
        # TODO: add 'inclusive' to include all ratings within sub-orgs/geos
        # TODO: add 'inherited' to point to a different context for ratings
        if aggregation not in self.AGGREGATIONS:
            raise InvalidAggregation(aggregation=aggregation)
        if ((rating is None and weight is not None) or
                (rating is not None and weight is None)):
            raise InconsistentArguments(arg1_name='rating', arg1_value=rating,
                                        art2_name='weight', arg2_value=weight)
        if (ratings is not None and rating is not None):
            ratings_str = '<{type} of length {length}>'.format(
                type=type(ratings), length=len(list(ratings)))
            raise InconsistentArguments(
                arg1_name='ratings', arg1_value=ratings_str,
                art2_name='rating', arg2_value=rating)

        if ratings:
            rating, weight = (
                AggregateProblemConnectionRating.calculate_values(ratings))

        elif rating is None:
            if aggregation == self.STRICT:
                rq = ProblemConnectionRating.query.filter_by(
                    connection=connection, problem=problem, org=org, geo=geo)
                # TODO: implement inclusive aggregation
                # Removed since it is not strict:
                # rq = rq.filter_by(org=org) if org else rq
                # rq = rq.filter_by(geo=geo) if geo else rq
                # ratings = rq.all()
                rating, weight = (
                    AggregateProblemConnectionRating.calculate_values(rq))

        for field, value in (('Rating', rating), ('Weight', weight)):
            if not isinstance(value, Real):
                raise TypeError(
                    '{field} value of {value} is not a Real number.'
                    .format(field=field, value=value))

        if not ((rating >= self.MIN_RATING and rating <= self.MAX_RATING) or
                rating == self.NO_RATING):
            raise InvalidAggregateConnectionRating(rating=rating,
                                                   connection=connection)

        self.community = community
        self.connection = connection
        self.aggregation = aggregation
        self.rating = rating
        self.weight = weight

    def modify(self, **kwds):
        '''
        Modify an existing aggregate rating

        Modify the rating and/or weight if new values are provided and
        flag the aggregate problem connection rating as modified.
        Required by the Trackable metaclass.
        '''
        rating = kwds.get('rating', None)
        weight = kwds.get('weight', None)

        for field, value in (('Rating', rating), ('Weight', weight)):
            if not isinstance(value, Real):
                raise TypeError(
                    '{field} value of {value} is not a Real number.'
                    .format(field=field, value=value))

        if not ((rating >= 0 and rating <= 4) or rating == -1):
            raise InvalidAggregateConnectionRating(rating=rating,
                                                   connection=self.connection)
        if rating != self.rating or weight != self.weight:
            self.rating, self.weight = rating, weight
            self._modified.add(self)

    def display(self):
        '''Display (old custom __str__ method)'''
        cls_name = self.__class__.__name__
        problem, org, geo = self.community.derive_key()
        p_name = self.community.problem.name
        conn = self.connection
        is_causal = conn.axis == conn.CAUSAL
        p_a = conn.driver.name if is_causal else conn.broader.name
        if p_name == p_a:
            conn_str = conn.display().replace(p_name, '@' + p_name, 1)
        else:
            conn_str = ('@' + p_name).join(conn.display().rsplit(p_name, 1))
        return ('{cls}: {rating:.2f} with {weight:.2f} weight ({agg})\n'
                '  on {conn}\n'
                '  {org}{geo}'.format(
                    cls=cls_name,
                    rating=self.rating,
                    weight=self.weight,
                    agg=self.aggregation,
                    conn=conn_str,
                    org=''.join(('at ', org, ' ')) if org else '',
                    geo=''.join(('in ', geo.display())) if geo else ''))


class ProblemConnectionRating(BaseProblemModel):
    '''
    Base class for problem connection ratings

    Problem connection ratings are input by users within the context of
    a problem, org, and geo. For example, it is perfectly valid for the
    same user to provide a different rating of A -> B from the context
    of problem A vs. problem B because the perceived importance of B as
    an impact of A may be quite different from the perceived importance
    of A as a driver of B.

    Maintain problem/org/geo rather than substitute with community as
    this will most likely become a separate microservice and this extra
    granularity may be useful.
    '''
    SUB_BLUEPRINT = 'connection_ratings'

    MIN_RATING = 0
    MAX_RATING = 4
    MIN_WEIGHT = 0
    MAX_WEIGHT = 1000

    # TODO: replace with problem_human_id and remove relationship
    problem_id = Column(types.Integer, ForeignKey('problem.id'))
    problem = orm.relationship('Problem')

    # TODO: replace with org_human_id
    org = Column(types.String(256))

    # TODO: replace with geo_human_id and remove relationship
    geo_id = Column(types.Integer, ForeignKey('geo.id'))
    geo = orm.relationship('Geo')

    # TODO: replace with other_problem_human_id and connection_category
    # and remove relationship. Connection category values include
    # drivers, impacts, broader, narrower; allows retrieving all ratings
    # in a community with a single query
    connection_id = Column(types.Integer, ForeignKey('problem_connection.id'))
    connection = orm.relationship('ProblemConnection',
                                  back_populates='ratings')

    connection_category = Column(types.String(16))

    # TODO: replace with user_id
    user = Column(types.String(60))

    _rating = Column('rating', types.Integer)
    _weight = Column('weight', types.Integer)

    # Querying use cases:
    #
    # 1. The Problem Page needs weighted average ratings on each connection
    #    to order them and modulate how they are displayed. This may end
    #    up being pre-processed, but it must be queried when calculated.
    #    cols: problem_id, org, geo, connection_id
    #       where most commonly org is None
    #    cols: problem_id, org, geo
    #
    # 2. The Problem Page needs to ask the user to rate connections that
    #    the user has not yet rated).
    #    cols: user, problem_id, org, geo
    #
    # 3. The Personal Dashboard needs to track history of all the user's
    #    inputs including connection ratings.
    #    cols: user
    #
    # __table_args__ = (UniqueConstraint('problem_id',
    #                                    'connection_id',
    #                                    'org',
    #                                    'geo',
    #                                    'user',
    #                                    name='uq_problem_connection_rating'),)
    #
    __table_args__ = (Index('ux_problem_connection_rating',
                            # ux for unique index
                            'problem_id',
                            'connection_id',
                            'org',
                            'geo_id',
                            'user',
                            unique=True),
                      Index('ix_problem_connection_rating:user+problem_id',
                            # ix for index
                            'user',
                            'problem_id',
                            'org',
                            'geo_id'),)

    Key = namedtuple('ProblemConnectionRatingKey',
                     'connection, problem, org, geo, user')

    @classmethod
    def create_key(cls, connection, problem, org=None, geo=None,
                   user='Intertwine', **kwds):
        '''Create Trackable key for a problem connection rating'''
        return cls.Key(connection, problem, org, geo, user)

    def derive_key(self, **kwds):
        '''Derive key from a problem connection rating instance'''
        return self.__class__.Key(self.connection, self.problem, self.org,
                                  self.geo, self.user)

    @property
    def rating(self):
        return self._rating

    @rating.setter
    def rating(self, val):
        self.update_values(rating=val)

    rating = orm.synonym('_rating', descriptor=rating)

    @property
    def weight(self):
        return self._weight

    @weight.setter
    def weight(self, val):
        self.update_values(weight=val)

    weight = orm.synonym('_weight', descriptor=weight)

    def update_values(self, rating=None, weight=None):
        '''
        Update values

        Provides way to update both rating and weight at same time,
        since any change must be propagated to all affected aggregate
        ratings via the relevant communities.
        '''
        if rating is None and weight is None:
            raise ValueError('rating and weight cannot both be None')

        has_updated = False

        if rating is None:
            rating = old_rating = self.rating
        elif (not isinstance(rating, int) or
                rating < self.MIN_RATING or rating > self.MAX_RATING):
            raise InvalidProblemConnectionRating(rating=rating,
                                                 *self.derive_key())
        else:
            old_rating = self.rating if hasattr(self, '_rating') else None
            if rating != old_rating:
                self._rating = rating
                has_updated = True

        if weight is None:
            weight = old_weight = self.weight
        elif (not isinstance(weight, int) or
                weight < self.MIN_WEIGHT or weight > self.MAX_WEIGHT):
            raise InvalidProblemConnectionWeight(weight=weight,
                                                 *self.derive_key())
        else:
            old_weight = self.weight if hasattr(self, '_weight') else None
            if weight != old_weight:
                self._weight = weight
                has_updated = True

        if has_updated:
            from ..communities.models import Community

            community = Community.query.filter_by(problem=self.problem,
                                                  org=self.org,
                                                  geo=self.geo).first()
            if community:
                community.update_aggregate_ratings(connection=self.connection,
                                                   user=self.user,
                                                   new_user_rating=rating,
                                                   new_user_weight=weight,
                                                   old_user_rating=old_rating,
                                                   old_user_weight=old_weight)
        return has_updated

    def __init__(self, rating, connection, problem, org, geo,
                 user='Intertwine', weight=None):
        '''
        Initialize a new problem connection rating

        The connection parameter is an instance, problem and geo
        may be either instances or human_ids, and the rest are literals
        based on the JSON problem connection rating schema. The rating
        parameter must be an integer between 0 and 4 inclusive.
        '''
        if not isinstance(connection, ProblemConnection):
            raise InvalidEntity(variable='connection', value=connection,
                                classname='ProblemConnection')
        is_causal = connection.axis == connection.CAUSAL
        p_a = connection.driver if is_causal else connection.broader
        p_b = connection.impact if is_causal else connection.narrower
        if is_causal:
            self.connection_category = (connection.DRIVERS if problem is p_b
                                        else connection.IMPACTS)
        else:
            self.connection_category = (connection.BROADER if problem is p_b
                                        else connection.NARROWER)

        if isinstance(problem, basestring):
            problem_human_id = problem
            problem = Problem[problem_human_id]
            if not problem:
                raise KeyError('Problem does not exist for human_id {human_id}'
                               .format(human_id=problem_human_id))

        if problem not in (p_a, p_b):
            raise InvalidProblemForConnection(problem=problem,
                                              connection=connection)

        if isinstance(geo, basestring):
            geo_human_id = geo
            geo = Geo[geo_human_id]
            if not geo:
                raise KeyError('Geo does not exist for human_id {human_id}'
                               .format(human_id=geo_human_id))

        # TODO: take user instance in addition to user_id
        if user is None or user == '':
            raise InvalidUser(user=user, connection=connection)

        self.problem = problem
        self.connection = connection
        # TODO: make org an entity rather than a string
        self.org = org
        self.geo = geo
        self.user = user
        # weight = user.expertise(problem, org, geo)
        weight = 1 if weight is None else weight
        self.update_values(rating=rating, weight=weight)

    def modify(self, **kwds):
        '''
        Modify an existing problem connection rating

        Modify the rating field if a new value is provided and flag the
        problem connection rating as modified. Required by the Trackable
        metaclass.
        '''
        rating = kwds.get('rating', None)
        weight = kwds.get('weight', None)
        try:
            has_updated = self.update_values(rating=rating, weight=weight)
            if has_updated:
                self._modified.add(self)
        except ValueError:
            pass

    def display(self):
        '''Display (old custom __str__ method)'''
        p_name = self.problem.name
        conn = self.connection
        is_causal = conn.axis == conn.CAUSAL
        p_a = conn.driver.name if is_causal else conn.broader.name
        if p_name == p_a:
            conn_str = conn.display().replace(p_name, '@' + p_name, 1)
        else:
            conn_str = ('@' + p_name).join(conn.display().rsplit(p_name, 1))
        org = self.org
        geo = self.geo
        return ('{cls}: {rating} by {user} with {weight} weight\n'
                '  on {conn}\n'
                '  {org}{geo}'.format(
                    cls=self.__class__.__name__,
                    rating=self.rating,
                    user=self.user,
                    weight=self.weight,
                    conn=conn_str,
                    org=''.join(('at ', org, ' ')) if org else '',
                    geo=''.join(('in ', geo.display())) if geo else ''))


class ProblemConnection(BaseProblemModel):
    '''
    Base class for problem connections

    A problem connection is uniquely defined by its axis ('causal' or
    'scoped') and the two problems it connects: problem_a and problem_b.

    In causal connections, problem_a drives problem_b, so problem_a is
    the 'driver' and problem_b is the 'impact' in the database
    relationships. (Of course, this means from the perspective
    of the driver, the given connection is in the 'impacts' field.)

    In scoped connections, problem_a is broader than problem_b, so
    problem_a is 'broader' and problem_b is 'narrower' in the database
    relationships. (Again, this means from the perspective of the
    broader problem, the given connection is in the 'narrower' field.)

                  'causal'                          'scoped'

                                                    problem_a
        problem_a    ->    problem_b               ('broader')
        ('driver')         ('impact')                  ::
                                                    problem_b
                                                   ('narrower')
    '''
    SUB_BLUEPRINT = 'connections'
    AXIS, CAUSAL, SCOPED = 'axis', 'causal', 'scoped'
    AXES = {CAUSAL, SCOPED}
    DRIVER, IMPACT = 'driver', 'impact'
    DRIVERS, IMPACTS = 'drivers', 'impacts'
    BROADER, NARROWER = 'broader', 'narrower'
    ADJACENT_PROBLEM, SELF = 'adjacent_problem', 'self'
    PROBLEM_A, PROBLEM_B = 'problem_a', 'problem_b'
    PROBLEM_A_ID, PROBLEM_B_ID = 'problem_a_id', 'problem_b_id'
    RELATIVE_A, RELATIVE_B = 'relative_a', 'relative_b'
    CATEGORY, INVERSE_CATEGORY = 'category', 'inverse_category'
    COMPONENT, INVERSE_COMPONENT = 'component', 'inverse_component'
    COMPONENT_ID, INVERSE_COMPONENT_ID = 'component_id', 'inverse_component_id'

    axis = Column(types.String(6))
    problem_a_id = Column(types.Integer, ForeignKey('problem.id'))
    problem_b_id = Column(types.Integer, ForeignKey('problem.id'))
    # TODO: remove ratings relationship
    ratings = orm.relationship('ProblemConnectionRating',
                               back_populates='connection',
                               lazy='dynamic')

    aggregate_ratings = orm.relationship('AggregateProblemConnectionRating',
                                         back_populates='connection',
                                         lazy='dynamic')

    __table_args__ = (Index('ux_problem_connection',
                            # ux for unique index
                            PROBLEM_A_ID,
                            AXIS,
                            PROBLEM_B_ID,
                            unique=True),
                      Index('ix_problem_connection:{problem_b_id}+{axis}'
                            .format(problem_b_id=PROBLEM_B_ID, axis=AXIS),
                            # ix for index
                            PROBLEM_B_ID,
                            AXIS),)

    CategoryMapRecord = namedtuple(
        'ProblemConnection_CategoryMapRecord',
        (AXIS, CATEGORY, COMPONENT, COMPONENT_ID, RELATIVE_A, RELATIVE_B,
            INVERSE_COMPONENT_ID, INVERSE_COMPONENT, INVERSE_CATEGORY))

    CATEGORY_MAP = OrderedDict((
        (DRIVERS, CategoryMapRecord(
            CAUSAL, DRIVERS, DRIVER, PROBLEM_A_ID, ADJACENT_PROBLEM,
            SELF, PROBLEM_B_ID, IMPACT, IMPACTS)),
        (IMPACTS, CategoryMapRecord(
            CAUSAL, IMPACTS, IMPACT, PROBLEM_B_ID, SELF,
            ADJACENT_PROBLEM, PROBLEM_A_ID, DRIVER, DRIVERS)),
        (BROADER, CategoryMapRecord(
            SCOPED, BROADER, BROADER, PROBLEM_A_ID, ADJACENT_PROBLEM,
            SELF, PROBLEM_B_ID, NARROWER, NARROWER)),
        (NARROWER, CategoryMapRecord(
            SCOPED, NARROWER, NARROWER, PROBLEM_B_ID, SELF,
            ADJACENT_PROBLEM, PROBLEM_A_ID, BROADER, BROADER))
    ))

    Key = namedtuple('ProblemConnectionKey', (AXIS, PROBLEM_A, PROBLEM_B))
    CausalKey = namedtuple('ProblemConnectionCausalKey',
                           (AXIS, DRIVER, IMPACT))
    ScopedKey = namedtuple('ProblemConnectionScopedKey',
                           (AXIS, BROADER, NARROWER))
    Problems = namedtuple('ProblemConnection_Problems', (PROBLEM_A, PROBLEM_B))

    @classmethod
    def create_key(cls, axis, problem_a, problem_b, **kwds):
        '''Create Trackable key, a CausalKey or ScopedKey based on axis'''
        return cls.Key(axis, problem_a, problem_b)

    def derive_key(self, generic=False, **kwds):
        '''Derive Trackable key, a CausalKey or ScopedKey based on axis'''
        cls = self.__class__  # TODO: Fix vardygrify so this isn't needed
        return cls.Key(self.axis, self.problem_a, self.problem_b)

    @classmethod
    def mutate_key(cls, key):
        axis, problem_a, problem_b = key
        if axis == cls.CAUSAL:
            return cls.CausalKey(axis, problem_a, problem_b)
        if axis == cls.SCOPED:
            return cls.ScopedKey(axis, problem_a, problem_b)

    @property
    def problem_a(self):
        return self.driver if self.axis == self.CAUSAL else self.broader

    @property
    def problem_b(self):
        return self.impact if self.axis == self.CAUSAL else self.narrower

    @property
    def problems(self):
        cls = self.__class__
        return (cls.Problems(self.driver, self.impact)
                if self.axis == self.CAUSAL
                else cls.Problems(self.broader, self.narrower))

    def derive_category(self, problem):
        '''Derive connection category, given a problem'''
        is_causal = self.axis == self.CAUSAL
        p_a = self.driver if is_causal else self.broader
        p_b = self.impact if is_causal else self.narrower

        if problem not in {p_a, p_b}:
            raise InvalidProblemForConnection(problem=problem,
                                              connection=self)
        category = (
            (self.DRIVERS if problem is p_b else self.IMPACTS)
            if is_causal else
            (self.BROADER if problem is p_b else self.NARROWER))

        return category

    def __init__(self, axis, problem_a, problem_b,
                 ratings_data=None, ratings_context_problem=None):
        '''
        Initialize a new problem connection

        Required inputs include axis, a string with value 'causal' or
        'scoped' and two problem instances or problem names. An axis of
        'causal' means problem_a is a driver of problem_b, while an axis
        of 'scoped' means problem_a is broader than problem_b. If a
        problem name is provided and no matching problem exists, a new
        problem is created.

        The optional ratings_data parameter is a list of ratings based
        on the JSON problem connection rating schema. The problem
        parameter must be provided if ratings_data is specified, as it
        is required to define a problem connection rating.
        '''
        # TODO: make axis an Enum
        if axis not in self.AXES:
            raise InvalidConnectionAxis(axis=axis, valid_axes=self.AXES)
        if problem_a is problem_b:
            raise CircularConnection(problem=problem_a)
        self.axis = axis
        is_causal = self.axis == self.CAUSAL

        problems = []
        for problem in (problem_a, problem_b):
            if not problem:
                raise ValueError('Invalid problem or problem name: {p}'
                                 .format(p=problem))
            if isinstance(problem, basestring):
                problem_name = problem
                problem_key = Problem.create_key(name=problem_name)
                try:
                    problem = Problem[problem_key]
                except KeyError:
                    problem = Problem(problem_name)
            problems.append(problem)

        problem_a, problem_b = problems

        self.driver = problem_a if is_causal else None
        self.impact = problem_b if is_causal else None
        self.broader = problem_a if not is_causal else None
        self.narrower = problem_b if not is_causal else None
        self.ratings = []
        self.aggregate_ratings = []

        if ratings_data and ratings_context_problem:
            self.load_ratings(ratings_data, ratings_context_problem)

    def modify(self, **kwds):
        '''
        Modify an existing problem connection

        Append any new problem connection ratings to the ratings field
        if problem and ratings_data are specified. If a rating is
        added, flag the connection as modified (via load_ratings). No
        other fields may be modified. Required by the Trackable
        metaclass.
        '''
        ratings_data = kwds.get('ratings_data', None)
        ratings_context_problem = kwds.get('ratings_context_problem', None)
        if ratings_data and ratings_context_problem:
            self.load_ratings(ratings_data, ratings_context_problem)

    def load_ratings(self, ratings_data, ratings_context_problem):
        '''
        Load a problem connection's ratings

        For each rating in the ratings_data, if the rating does not
        already exist, create it, else update it. Newly created ratings
        are appended to the 'ratings' field of the problem connection.
        If a rating is added, flag the connection as modified.
        '''
        rating_added = False
        for rating_data in ratings_data:
            geo_huid = rating_data.pop('geo')
            geo = Geo[geo_huid]
            connection_rating = ProblemConnectionRating(
                connection=self,
                problem=ratings_context_problem,
                geo=geo,
                **rating_data)
            # TODO: add tracking of new to Trackable and check it here
            if connection_rating not in self.ratings:
                self.ratings.append(connection_rating)
                rating_added = True
        if rating_added and hasattr(self, '_modified'):
            self._modified.add(self)

    def display(self):
        '''Display (old custom __str__ method)'''
        is_causal = self.axis == self.CAUSAL
        ct = '->' if is_causal else '::'
        p_a = self.driver.name if is_causal else self.broader.name
        p_b = self.impact.name if is_causal else self.narrower.name
        return '{p_a} {ct} {p_b}'.format(p_a=p_a, ct=ct, p_b=p_b)


class Problem(BaseProblemModel):
    '''
    Base class for problems

    Problems and the connections between them are global in that they
    don't vary by region or organization. However, the ratings of the
    connections DO vary by organization, geo, and problem context.

    Problem instances are Trackable (metaclass), where the registry
    keys are the problem names in lowercase with underscores instead of
    spaces.

    Problems can connect to other problems in four ways:

                               broader
                                  ::
                    drivers -> problem -> impacts
                                  ::
                               narrower

    Drivers/impacts are 'causal' connections while broader/narrower are
    'scoped' connections.
    '''
    HUMAN_ID = 'human_id'

    _name = Column('name', types.String(60), index=True, unique=True)
    _human_id = Column(HUMAN_ID, types.String(60), index=True, unique=True)
    definition = Column(types.String(200))
    definition_url = Column(types.String(2048))
    # TODO: support multiple sponsors in different org/geo contexts
    sponsor = Column(types.String(60))
    images = orm.relationship(
        'Image',
        back_populates='problem',
        lazy='dynamic')
    drivers = orm.relationship(
        'ProblemConnection',
        primaryjoin=(('and_(Problem.id==ProblemConnection.{problem_b_id}, '
                      'ProblemConnection.axis=="{causal}")')
                     .format(problem_b_id=ProblemConnection.PROBLEM_B_ID,
                             causal=ProblemConnection.CAUSAL)),
        backref=ProblemConnection.IMPACT,
        lazy='dynamic',
        cascade='delete, delete-orphan')
    impacts = orm.relationship(
        'ProblemConnection',
        primaryjoin=(('and_(Problem.id==ProblemConnection.{problem_a_id}, '
                      'ProblemConnection.axis=="{causal}")')
                     .format(problem_a_id=ProblemConnection.PROBLEM_A_ID,
                             causal=ProblemConnection.CAUSAL)),
        backref=ProblemConnection.DRIVER,
        lazy='dynamic',
        cascade='delete, delete-orphan')
    broader = orm.relationship(
        'ProblemConnection',
        primaryjoin=(('and_(Problem.id==ProblemConnection.{problem_b_id}, '
                      'ProblemConnection.axis=="{scoped}")')
                     .format(problem_b_id=ProblemConnection.PROBLEM_B_ID,
                             scoped=ProblemConnection.SCOPED)),
        backref=ProblemConnection.NARROWER,
        lazy='dynamic',
        cascade='delete, delete-orphan')
    narrower = orm.relationship(
        'ProblemConnection',
        primaryjoin=(('and_(Problem.id==ProblemConnection.{problem_a_id}, '
                      'ProblemConnection.axis=="{scoped}")')
                     .format(problem_a_id=ProblemConnection.PROBLEM_A_ID,
                             scoped=ProblemConnection.SCOPED)),
        backref=ProblemConnection.BROADER,
        lazy='dynamic',
        cascade='delete, delete-orphan')

    # URL Guidance: perishablepress.com/stop-using-unsafe-characters-in-urls
    # Exclude unsafe:            "<>#%{}|\^~[]`
    # Exclude reserved:          ;/?:@=&
    # Exclude space placeholder: _
    # Exclude unnecessary:       !*
    # Include safe plus space:   -+.,$'() a-zA-Z0-9
    name_pattern = re.compile(r'''^[-+.,$'() a-zA-Z0-9]+$''')

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val):
        name = titlecase(val.strip())
        if Problem.name_pattern.match(name) is None:  # check for valid name
            raise NameError("'{}' is not a valid problem name.".format(name))
        self.human_id = self.convert_name_to_human_id(name)  # set the human_id
        self._name = name  # set the name last

    name = orm.synonym('_name', descriptor=name)

    @property
    def human_id(self):
        return self._human_id

    @human_id.setter
    def human_id(self, val):
        if val is None:
            raise ValueError('human_id cannot be set to None')
        cls = self.__class__
        cls.validate_against_sub_blueprints(human_id=val, include=False)
        # During __init__()
        if self._human_id is None:
            self._human_id = val
            return
        # Not during __init__()
        key = cls.Key(human_id=val)
        self.register_update(key)

    human_id = orm.synonym('_human_id', descriptor=human_id)

    Key = namedtuple('ProblemKey', (HUMAN_ID,))

    @classmethod
    def create_key(cls, human_id=None, name=None, **kwds):
        '''
        Create key for a problem

        Return a registry key allowing the Trackable metaclass to look
        up a problem instance. The key is created from the given name
        parameter.
        '''
        human_id = human_id if human_id else cls.convert_name_to_human_id(name)
        return cls.Key(human_id)

    def derive_key(self, **kwds):
        '''
        Derive key from a problem instance

        Return the registry key used by the Trackable metaclass from a
        problem instance. The key is derived from the human_id field on
        the problem instance.
        '''
        return self.__class__.Key(self.human_id)

    @staticmethod
    def convert_name_to_human_id(name):
        return name.strip().lower().replace(' ', '_')

    @staticmethod
    def infer_name_from_human_id(human_id):
        '''Infer name from key assuming ordinary titlecase rules'''
        return titlecase(human_id.replace('_', ' '))

    def __init__(self, name, definition=None, definition_url=None,
                 sponsor=None, images=[],
                 drivers=[], impacts=[], broader=[], narrower=[]):
        '''
        Initialize a new problem

        Inputs are key-value pairs based on the JSON problem schema.
        '''
        self.name = name
        self.definition = definition.strip() if definition else None
        self.definition_url = (urlnorm.norm(definition_url)
                               if definition_url else None)
        self.sponsor = sponsor.strip() if sponsor else None
        self.images = []
        self.drivers = []
        self.impacts = []
        self.broader = []
        self.narrower = []

        for image_url in images:
            image = Image(url=image_url, problem=self)
            if image not in self.images:
                self.images.append(image)

        # track problems modified by the creation of this problem via
        # new connections to existing problems
        self._modified = set()
        problem_connection_data = {ProblemConnection.DRIVERS: drivers,
                                   ProblemConnection.IMPACTS: impacts,
                                   ProblemConnection.BROADER: broader,
                                   ProblemConnection.NARROWER: narrower}
        for k, v in problem_connection_data.items():
            self.load_connections(category=k, data=v)

    def modify(self, **kwds):
        '''
        Modify an existing problem

        Inputs are key-value pairs based on the JSON problem schema.
        Modify the definition and definition_url if new values differ
        from existing values. Append any new images and problem
        connections (the latter within drivers, impacts, broader, and
        narrower). Track all problems modified, whether directly or
        indirectly through new connections.

        New problem connections and ratings are added while existing
        ones are updated (via load_connections). Required by the
        Trackable metaclass.
        '''
        for k, v in kwds.items():
            if k == 'name':
                continue  # name cannot be updated via upload
            elif k == 'definition':
                definition = v.strip() if v else None
                if definition != self.definition:
                    self.definition = definition
                    self._modified.add(self)
            elif k == 'definition_url':
                definition_url = v.strip() if v else None
                if definition_url != self.definition_url:
                    self.definition_url = definition_url
                    self._modified.add(self)
            elif k == 'sponsor':
                sponsor = v.strip() if v else None
                if sponsor != self.sponsor:
                    self.sponsor = sponsor
                    self._modified.add(self)
            elif k == 'images':
                image_urls = v if v else []
                for image_url in image_urls:
                    image = Image(url=image_url, problem=self)
                    if image not in self.images:
                        self.images.append(image)
                        self._modified.add(self)
            elif k in ProblemConnection.CATEGORY_MAP.keys():
                self.load_connections(category=k, data=v)
            else:
                raise NameError('{} not found.'.format(k))

    def load_connections(self, category, data):
        '''
        Load a problem's drivers, impacts, broader, or narrower

        The connections_name is the field name for a set of connections
        on a problem, either 'drivers', 'imapcts', 'broader', or
        'narrower'. The connections_data is the corresponding JSON data.
        The method loads the data and flags the set of problems
        modified in the process (including those that are also new).
        '''
        cat_map = ProblemConnection.CATEGORY_MAP[category]
        axis, inverse_category = cat_map.axis, cat_map.inverse_category
        p_a, p_b = cat_map.relative_a, cat_map.relative_b

        connections = getattr(self, category)

        for connection_data in data:
            adjacent_name = connection_data.get('adjacent_problem', None)
            adjacent_problem = Problem(name=adjacent_name)
            ratings_data = connection_data.get('problem_connection_ratings',
                                               [])
            connection = ProblemConnection(
                axis=axis,
                problem_a=locals()[p_a],
                problem_b=locals()[p_b],
                ratings_data=ratings_data,
                ratings_context_problem=self)
            if connection not in connections:
                connections.append(connection)
                getattr(adjacent_problem, inverse_category).append(connection)
                self._modified.add(adjacent_problem)

        if len(self._modified) > 0:
            self._modified.add(self)

    def connections(self):
        '''
        Connections

        Returns a generator that iterates through all the problem's
        connections
        '''
        # ['impact', 'driver', 'narrower', 'broader']
        categories = map(attrgetter(ProblemConnection.INVERSE_COMPONENT),
                         ProblemConnection.CATEGORY_MAP.values())

        return ProblemConnection.query.filter(or_(
            *map(lambda x: getattr(ProblemConnection, x) == self, categories)))

    def connections_by_category(self):
        '''
        Connections by category

        Returns an ordered dictionary of connection queries keyed by
        category that iterate alphabetically by the name of the
        adjoining problem. The category order is specified by the
        problem connection category map.
        '''
        PC = ProblemConnection
        connections = OrderedDict()
        for category in PC.CATEGORY_MAP:
            component = getattr(PC, PC.CATEGORY_MAP[category].component)
            connections[category] = (getattr(self, category).join(component)
                                     .order_by(Problem.name))
        return connections

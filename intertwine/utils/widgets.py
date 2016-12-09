#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
from collections import OrderedDict, namedtuple
from operator import eq, itemgetter

if sys.version.startswith('3'):
    imap = map
else:
    from itertools import imap


class Sentinel(object):
    _id = 0

    def __init__(self):
        self.id = self.__class__._id
        self.__class__._id += 1

    def __repr__(self):
        return '<{cls}: {id}>'.format(cls=self.__class__.__name__, id=self.id)


class InsertableOrderedDict(object):
    '''Reimplementation of OrderedDict that supports insertion'''
    sentinel = Sentinel()
    ValueTuple = namedtuple('InsertableOrderedDictValueTuple',
                            'value, next, prior')

    def _initialize(self, _iter_or_map, _as_iter):
        self._iod = {}
        s = self.sentinel
        keygetter = itemgetter(0) if _as_iter else lambda x: x
        valgetter = itemgetter(1) if _as_iter else lambda x: _iter_or_map[x]
        peekable = PeekableIterator(_iter_or_map, sentinel=s)
        self._beg = keygetter(peekable.peek()) if peekable.has_next() else s
        prior_key = s
        for obj in peekable:
            key, value = keygetter(obj), valgetter(obj)
            if self._iod.get(key, s) is not s:
                raise KeyError(u"Duplicate key: '{}'".format(key))
            next_key = keygetter(peekable.peek()) if peekable.has_next() else s
            self._iod[key] = (value, next_key, prior_key)
            prior_key = key
        self._end = key if self._beg is not s else s

    def __init__(self, _iter_or_map=(), *args, **kwds):
        try:
            self._initialize(_iter_or_map, _as_iter=True)
        except IndexError:
            self._initialize(_iter_or_map, _as_iter=False)
        super(InsertableOrderedDict, self).__init__(*args, **kwds)

    def insert(self, insert_key, key, value, after=False):
        '''insert a key/value pair

        I/O:
        insert_key  Reference key used for insertion
        key         Key to be inserted
        value       Value to be inserted
        after=False If True, inserts after reference key
        return      None
        '''
        if after:
            next_key = self._iod[insert_key][1]
            prior_key = insert_key
        else:
            next_key = insert_key
            prior_key = self._iod[insert_key][-1]

        self._insert_between(next_key=next_key, prior_key=prior_key,
                             key=key, value=value)

    def append(self, key, value):
        self._insert_between(next_key=self.sentinel, prior_key=self._end,
                             key=key, value=value)

    def prepend(self, key, value):
        self._insert_between(next_key=self._beg, prior_key=self.sentinel,
                             key=key, value=value)

    def _insert_between(self, next_key, prior_key, key, value):
        if self.get(key, self.sentinel) is not self.sentinel:
            raise KeyError(u"Key already exists: '{}'".format(key))

        self._iod[key] = value, next_key, prior_key

        if next_key is not self.sentinel:
            next_item = self._iod[next_key]
            self._iod[next_key] = (next_item[0], next_item[1], key)
        else:
            self._end = key

        if prior_key is not self.sentinel:
            prior_item = self._iod[prior_key]
            self._iod[prior_key] = (prior_item[0], key, prior_item[-1])
        else:
            self._beg = key

    def copy(self):
        return self.__class__(self)

    def __repr__(self):
        cls = self.__class__.__name__
        return u'{cls}({tuples})'.format(cls=cls, tuples=tuple(self.items()))

    def __len__(self):
        return len(self._iod)

    def __getitem__(self, key):
        return self._iod[key][0]

    def __setitem__(self, key, value):
        try:
            item = self._iod[key]
            self._iod[key] = (value, item[1], item[-1])
        except KeyError:
            self.append(key, value)

    def __delitem__(self, key):
        _, next_key, prior_key = self._iod[key]
        if next_key is not self.sentinel:
            next_item = self._iod[next_key]
            self._iod[next_key] = (next_item[0], next_item[1], prior_key)
        else:
            self._end = prior_key

        if prior_key is not self.sentinel:
            prior_item = self._iod[prior_key]
            self._iod[prior_key] = (prior_item[0], next_key, prior_item[-1])
        else:
            self._beg = next_key

        del self._iod[key]

    def __contains__(self, key):
        return key in self._iod

    def has_key(self, key):
        return key in self._iod

    def get(self, key, default=None):
        item = self._iod.get(key, self.sentinel)
        return item[0] if item is not self.sentinel else default

    def clear(self):
        self._iod.clear()
        self._beg = self.sentinel
        self._end = self.sentinel

    def __iter__(self):
        key = self._beg
        while key is not self.sentinel:
            yield key
            key = self._iod[key][1]

    def __reversed__(self):
        key = self._end
        while key is not self.sentinel:
            yield key
            key = self._iod[key][-1]

    def reverse(self):
        for key, item in self._iod.items():
            self._iod[key] = (item[0], item[-1], item[1])
        self._beg, self._end = self._end, self._beg

    def items(self):
        key = self._beg
        while key is not self.sentinel:
            yield (key, self._iod[key][0])
            key = self._iod[key][1]

    def keys(self):
        return self.__iter__()

    def values(self):
        key = self._beg
        while key is not self.sentinel:
            yield self._iod[key][0]
            key = self._iod[key][1]

    # def items(self):
    #     return [item for item in self.iteritems()]

    # def keys(self):
    #     return [key for key in self.iterkeys()]

    # def values(self):
    #     return [value for value in self.itervalues()]

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        if isinstance(other, (OrderedDict, InsertableOrderedDict)):
            return all(imap(eq, self.items(), other.items()))
        return all((eq(self[key], other.get(key)) for key in self))

    def __ne__(self, other):
        return not self.__eq__(other)


class PeekableIterator(object):
    '''Iterable that supports peeking at the next item'''
    def __init__(self, iterable, sentinel=object(), *args, **kwds):
        self.iterable = iter(iterable)
        self.sentinel = sentinel
        self.next_item = next(self.iterable, self.sentinel)
        super(PeekableIterator, self).__init__(*args, **kwds)

    def next(self):
        rv = self.next_item
        self.next_item = next(self.iterable, self.sentinel)
        return rv

    def has_next(self):
        return self.next_item is not self.sentinel

    def peek(self):
        return self.next_item

    def __iter__(self):
        while self.has_next():
            yield self.next()
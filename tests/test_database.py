#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pytest


@pytest.mark.unit
@pytest.mark.smoke
def test_app_created(options):
    '''Tests that a working app is created'''
    import flask
    from intertwine import create_app

    config = options['config']
    app = create_app(config)
    assert 'SERVER_NAME' in app.config
    server = '{}:{}'.format(options['host'], options['port'])
    host = (app.config.get('SERVER_NAME') or server).split(':')[0]
    port = (app.config.get('SERVER_NAME') or server).split(':')[-1]
    app.config['SERVER_NAME'] = '{}:{}'.format(host, port)

    with app.app_context():
        rv = flask.url_for('index')
        assert rv == 'http://{}:{}/'.format(host, port)


@pytest.mark.unit
@pytest.mark.smoke
def test_database_created(options):
    '''Tests that database is created'''
    import os
    from intertwine import create_app

    config = options['config']
    app = create_app(config)
    filepath = app.config['DATABASE'].split('///')[-1]
    if os.path.exists(filepath):
        os.remove(filepath)
    assert 'SERVER_NAME' in app.config
    server = '{}:{}'.format(options['host'], options['port'])
    host = (app.config.get('SERVER_NAME') or server).split(':')[0]
    port = (app.config.get('SERVER_NAME') or server).split(':')[-1]
    app.config['SERVER_NAME'] = '{}:{}'.format(host, port)

    with app.app_context():
        assert os.path.exists(filepath)



@pytest.mark.unit
@pytest.mark.smoke
def test_table_generation(options):
    '''Tests decoding incrementally'''
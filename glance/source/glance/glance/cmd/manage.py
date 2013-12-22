#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Glance Management Utility
"""

from __future__ import print_function

# FIXME(sirp): When we have glance-admin we can consider merging this into it
# Perhaps for consistency with Nova, we would then rename glance-admin ->
# glance-manage (or the other way around)

import os
import sys

# If ../glance/__init__.py exists, add ../ to Python search path, so that
# it will override what happens to be installed in /usr/(local/)lib/python...
possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(possible_topdir, 'glance', '__init__.py')):
    sys.path.insert(0, possible_topdir)

from oslo.config import cfg

from glance.common import config
from glance.common import exception
import glance.db.sqlalchemy.api
from glance.db.sqlalchemy import migration
from glance.openstack.common import log

CONF = cfg.CONF


# Decorators for actions
def args(*args, **kwargs):
    def _decorator(func):
        func.__dict__.setdefault('args', []).insert(0, (args, kwargs))
        return func
    return _decorator


class DbCommands(object):
    """Class for managing the db"""

    def __init__(self):
        pass

    def version(self):
        """Print database's current migration level"""
        print(migration.db_version())

    @args('--version', metavar='<version>', help='Database version')
    def upgrade(self, version=None):
        """Upgrade the database's migration level"""
        migration.upgrade(version)

    @args('--version', metavar='<version>', help='Database version')
    def downgrade(self, version=None):
        """Downgrade the database's migration level"""
        migration.downgrade(version)

    @args('--version', metavar='<version>', help='Database version')
    def version_control(self, version=None):
        """Place a database under migration control"""
        migration.version_control(version)

    @args('--version', metavar='<version>', help='Database version')
    @args('--current_version', metavar='<version>',
          help='Current Database version')
    def sync(self, version=None, current_version=None):
        """
        Place a database under migration control and upgrade,
        creating first if necessary.
        """
        migration.db_sync(version, current_version)


def add_legacy_command_parsers(command_object, subparsers):

    parser = subparsers.add_parser('db_version')
    parser.set_defaults(action_fn=command_object.version)

    parser = subparsers.add_parser('db_upgrade')
    parser.set_defaults(action_fn=command_object.upgrade)
    parser.add_argument('version', nargs='?')

    parser = subparsers.add_parser('db_downgrade')
    parser.set_defaults(action_fn=command_object.downgrade)
    parser.add_argument('version')

    parser = subparsers.add_parser('db_version_control')
    parser.set_defaults(action_fn=command_object.version_control)
    parser.add_argument('version', nargs='?')

    parser = subparsers.add_parser('db_sync')
    parser.set_defaults(action_fn=command_object.sync)
    parser.add_argument('version', nargs='?')
    parser.add_argument('current_version', nargs='?')


def add_command_parsers(subparsers):
    command_object = DbCommands()

    parser = subparsers.add_parser('db')
    parser.set_defaults(command_object=command_object)

    category_subparsers = parser.add_subparsers(dest='action')

    for (action, action_fn) in methods_of(command_object):
        parser = category_subparsers.add_parser(action)

        action_kwargs = []
        for args, kwargs in getattr(action_fn, 'args', []):
            # FIXME(basha): hack to assume dest is the arg name without
            # the leading hyphens if no dest is supplied
            kwargs.setdefault('dest', args[0][2:])
            if kwargs['dest'].startswith('action_kwarg_'):
                action_kwargs.append(
                    kwargs['dest'][len('action_kwarg_'):])
            else:
                action_kwargs.append(kwargs['dest'])
                kwargs['dest'] = 'action_kwarg_' + kwargs['dest']

            parser.add_argument(*args, **kwargs)

        parser.set_defaults(action_fn=action_fn)
        parser.set_defaults(action_kwargs=action_kwargs)

        parser.add_argument('action_args', nargs='*')

        add_legacy_command_parsers(command_object, subparsers)


command_opt = cfg.SubCommandOpt('command',
                                title='Commands',
                                help='Available commands',
                                handler=add_command_parsers)


def methods_of(obj):
    """Get all callable methods of an object that don't start with underscore

    returns a list of tuples of the form (method_name, method)
    """
    result = []
    for i in dir(obj):
        if callable(getattr(obj, i)) and not i.startswith('_'):
            result.append((i, getattr(obj, i)))
    return result


def main():
    CONF.register_cli_opt(command_opt)
    try:
        # We load the glance-registry config section because
        # sql_connection is only part of the glance registry.
        glance.db.sqlalchemy.api.add_cli_options()

        cfg_files = cfg.find_config_files(project='glance',
                                          prog='glance-registry')
        cfg_files.extend(cfg.find_config_files(project='glance',
                                               prog='glance-api'))
        config.parse_args(default_config_files=cfg_files,
                          usage="%(prog)s [options] <cmd>")
        log.setup('glance')
    except RuntimeError as e:
        sys.exit("ERROR: %s" % e)

    try:

        CONF.command.action_fn()
    except exception.GlanceException as e:
        sys.exit("ERROR: %s" % e)


if __name__ == '__main__':
    main()

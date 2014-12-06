#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render bobtemplates.plone hooks.
"""
from mrbob.bobexceptions import ValidationError

import os
import shutil
import sys


def to_boolean(configurator, question, answer):
    """
    If you want to convert an answer to Python boolean, you can
    use this function as :ref:`post-question-hook`:

    .. code-block:: ini

        [questions]
        idiot.question = Are you young?
        idiot.post_ask_question = mrbob.hooks:to_boolean

    Following variables can be converted to a boolean: **y, n, yes, no, true, false, 1, 0**
    """
    if isinstance(answer, bool):
        return answer
    value = answer.lower()
    if value in ['y', 'yes', 'true', '1']:
        return True
    elif value in ['n', 'no', 'false', '0']:
        return False
    else:
        raise ValidationError('Value must be a boolean (y/n)')


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def suggest_packagetype(configurator, question):
    """ Suggest the type of package form the name of the folder.
    """
    package_dir = configurator.target_directory.split('/')[-1]
    if len(package_dir.split('.')) == 3:
        packagetype = 'nested'
    else:
        packagetype = 'normal'
    question.default = packagetype


def after_packagetype(configurator, question, answer):
    """ Skip namespace2 for normal packages.
    """
    if answer.lower() == 'normal':
        configurator.variables['package.namespace2'] = False
    return answer.lower()


def suggest_namespace(configurator, question):
    package_dir = configurator.target_directory.split('/')[-1]
    namespace = package_dir.split('.')[0]
    question.default = namespace


def suggest_namespace2(configurator, question):
    package_dir = configurator.target_directory.split('/')[-1]
    namespace2 = package_dir.split('.')[1]
    question.default = namespace2


def suggest_name(configurator, question):
    package_dir = configurator.target_directory.split('/')[-1]
    name = package_dir.split('.')[-1]
    question.default = name


def validate_packagename(configurator, question, answer):
    """ Check if the target-dir and the package-name match.
    We allow this but ask if the user want's to continue?
    """
    nested = bool(configurator.variables['package.type'] == 'nested')
    package_dir = configurator.target_directory.split('/')[-1]
    if nested:
        package_name = "{0}.{1}.{2}".format(
            configurator.variables['package.namespace'],
            configurator.variables['package.namespace2'],
            answer)
    else:
        package_name = "{0}.{1}".format(
            configurator.variables['package.namespace'],
            answer)

    if not package_dir == package_name:
        msg = "Directory ({0}) and name ({1}) do not match. Continue anyway?"
        if not query_yes_no(msg.format(package_dir, package_name)):
            sys.exit("Aborted!")
    return answer


def post_profile(configurator, question, answer):
    """ Skip many questions if we have no profile.
    """
    value = to_boolean(configurator, question, answer)
    if not value:
        configurator.variables['package.theme'] = False
        configurator.variables['package.setuphandlers'] = False
        configurator.variables['package.testing'] = False
        configurator.variables['package.theme'] = False
        configurator.variables['travis.integration.enabled'] = False
        configurator.variables['travis.notifications.destination'] = False
        configurator.variables['travis.notifications.type'] = False
    return value


def post_testing(configurator, question, answer):
    """ Skip questions on travis if we have no profile.
    """
    value = to_boolean(configurator, question, answer)
    if not value:
        configurator.variables['travis.integration.enabled'] = False
        configurator.variables['travis.notifications.destination'] = False
        configurator.variables['travis.notifications.type'] = False
    return value


def post_travis(configurator, question, answer):
    """ Skip questions on travis.
    """
    value = to_boolean(configurator, question, answer)
    if not value:
        configurator.variables['travis.notifications.type'] = 'email'
        configurator.variables['travis.notifications.destination'] = 'test@plone.org'
    return value


def prepare_render(configurator):
    """Some variables to make templating easier.

    This is especially important for alowing nested and normal packages.
    """
    if configurator.variables['package.type'] == 'nested':
        dottedname = "{0}.{1}.{2}".format(
            configurator.variables['package.namespace'],
            configurator.variables['package.namespace2'],
            configurator.variables['package.name'])
    else:
        dottedname = "{0}.{1}".format(
            configurator.variables['package.namespace'],
            configurator.variables['package.name'])

    # package.dottedname = 'collective.foo.something'
    configurator.variables['package.dottedname'] = dottedname

    camelcasename = dottedname.replace('.', ' ').title().replace(' ', '')
    browserlayer = "{0}Layer".format(camelcasename)

    # package.browserlayer = 'CollectiveFooSomethingLayer'
    configurator.variables['package.browserlayer'] = browserlayer

    # package.longname = 'collectivefoosomething'
    configurator.variables['package.longname'] = camelcasename.lower()

    # jenkins.directories = 'collective/foo/something'
    configurator.variables['jenkins.directories'] = dottedname.replace('.', '/')

    # namespace_packages = "['collective', 'collective.foo']"
    if configurator.variables['package.type'] == 'nested':
        namespace_packages = "'{0}'".format(
            configurator.variables['package.namespace'])
    else:
        namespace_packages = "'{0}', '{0}.{1}'".format(
            configurator.variables['package.namespace'],
            configurator.variables['package.namespace2'])
    configurator.variables['package.namespace_packages'] = namespace_packages


def cleanup_package(configurator):
    """ Cleanup and make nested if needed.

    Transform into a nested package if that was the selected option.
    Remove parts that are not needed depending on the chosen configuration.
    """

    nested = bool(configurator.variables['package.type'] == 'nested')

    # construct full path '.../src/collective'
    start_path = "{0}/src/{1}".format(
        configurator.target_directory,
        configurator.variables['package.namespace'])

    # path for normal packages: '.../src/collective/myaddon'
    base_path = "{0}/{1}".format(
        start_path,
        configurator.variables['package.name'])

    if nested:
        # Modify the created package to be nested by adding a new folder
        # from namespace2 and moving the created stuff in there.

        # path for nested packages: '.../src/collective/behavior/myaddon'
        base_path_nested = "{0}/{1}/{2}".format(
            start_path,
            configurator.variables['package.namespace2'],
            configurator.variables['package.name'])

        namespace2 = configurator.variables['package.namespace2']
        newpath = "{0}/{1}".format(start_path, namespace2)
        if not os.path.exists(newpath):
            # create new directory '.../src/collective/behavior' and move
            os.makedirs(newpath)
            # copy the __init__.py into it
            shutil.copy2(
                "{0}/__init__.py".format(base_path),
                newpath)
            # move the whole 'myaddon'-directory into it
            shutil.move(base_path, base_path_nested)

        # use the new path for deleting
        base_path = base_path_nested

    # find out what to delete
    to_delete = []

    if not configurator.variables['package.profile']:
        to_delete.extend([
            "{0}/profiles",
            "{0}/testing.zcml",
            "{0}/setuphandlers.py",
            "{0}/interfaces.py",
        ])

    if not configurator.variables['package.setuphandlers']:
        to_delete.extend([
            "{0}/setuphandlers.py",
        ])

    if not configurator.variables['package.locales']:
        to_delete.extend([
            "{0}/locales",
        ])

    if not configurator.variables['package.example']:
        to_delete.extend([
            "{0}/browser/templates",
            "{0}/browser/views.py",
        ])

    if not configurator.variables['package.testing']:
        to_delete.extend([
            "{0}/tests",
            "{0}/testing.py",
            "{0}/testing.zcml",
            "{0}/.travis.yml",
            "{0}/travis.cfg",
            "{0}/.coveragerc",
            "{0}/profile/testing",
        ])

    if not configurator.variables['travis.integration.enabled']:
        to_delete.extend([
            "{0}/.travis.yml",
            "{0}/travis.cfg",
        ])

    if not configurator.variables['package.theme']:
        to_delete.extend([
            "{0}/theme",
            "{0}/profiles/default/theme.xml",
        ])

    # remove parts
    for path in to_delete:
        path = path.format(base_path)
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

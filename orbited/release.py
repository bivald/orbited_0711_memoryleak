#!/usr/bin/env python
""" A simple script to automate releasing orbited
"""
from optparse import OptionParser
import os
import subprocess
import sys

from hgutils import HgUtil

PYTHON = sys.executable
DAEMON_DIR = \
    os.path.join(os.path.abspath(os.path.dirname(__file__)), 'daemon')
                                        
def setup_py(command, args):
    cwd = DAEMON_DIR
    command = [PYTHON, 'setup.py', command] + args
    returncode = subprocess.call(" ".join(command), shell=True, cwd=cwd)
    return returncode
    
class SetupCfg(object):
    """ A context manager that will restore the local repository when it exits
    
        When SetupCfg is created it takes a list of 3-tuples that look like:
          (<setup.cfg section>, <option name>, <new value>)
        
        When the context is exited, an hg revert is applied to the local
        repository so that any changes made are erased.
    """
    
    def __init__(self, configuration_options):
        self._options = configuration_options
        self._hg = HgUtil('.')
        # if setup.cfg doesn't exist, we may create one. hg revert
        # won't delete the file so we need to know if we'll have to
        # later.
        self._setup_cfg_exists = os.path.exists('daemon/setup.cfg')

    def __enter__(self):
        for application, option, value in self._options:
            self._set_option(application, option, value)
       
    def __exit__(self, *args, **kwargs):
        if self._setup_cfg_exists:
            self._hg.revert('daemon/setup.cfg')
        else:
            os.remove('daemon/setup.cfg')
        # return False; we never have a reason to suppress an exception
        return False
    
    @staticmethod
    def _set_option(app, opt, value):
        print app, opt, value
        # use the setup.py setopt command to modify setup.cfg.
        args = ['--command', app,
                '--option', opt,
                '--set-value', value]
        return setup_py('setopt', args)
        
class ReleaseManager(object):
    
    def __init__(self, repository_path):
        self._path = repository_path
        self._hg = HgUtil(self._path)
    
    def make_release(self, type, upload=False):
        args = []
        if upload:
            args.append('upload')
        setup_py(type, args)
    
    def snapshot(self, type='sdist', upload=False):
        repo = HgUtil('.')
        revision = repo.revision
        dev_tag = '-dev-%(revision)s' % dict(revision=revision)
        with SetupCfg([('egg_info', 'tag_build', dev_tag)]):
            self.make_release(type, upload)

def make_parser():
    parser = OptionParser()
    parser.add_option('-u', '--upload', dest="upload",
                      default=False, action="store_true",
                      help="upload the package to the pypi")
    return parser

def main(argv):
    parser = make_parser()
    (options, args) = parser.parse_args(argv)
    script = args.pop(0) # throw this away
    if args:
        release_type = args[0]
    else:
        release_type = 'sdist'
    releaser = ReleaseManager('.')
    releaser.snapshot(release_type, options.upload)

if (__name__=='__main__'):
    main(sys.argv)

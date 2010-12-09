import subprocess

from mercurial import hg
from mercurial import ui

class HgUtil(object):
    
    def __init__(self, repository_path):
        self._ui = ui.ui()
        self._repo = hg.repository(self._ui, repository_path)
    
    @property
    def revision(self):
        return str(self._repo[None].parents()[0])
    
    def revert(self, *files):
        command = \
            'hg revert --no-backup %s' % " ".join(files)
        subprocess.call(command, shell=True)

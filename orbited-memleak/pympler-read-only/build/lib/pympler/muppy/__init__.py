"""Toolset for measuring the memory usage of Python applications.

Be aware that muppy will call gc.collect() whenever the object state is
gathered to remove reference cycles.

"""
import sys
if sys.hexversion < 0x2040000:
    raise NotImplementedError('pympler.muppy requires Python 2.4 or newer')

__all__ = ['refbrowser',
           'tracker',
           'summary']

from pympler.muppy import *

def print_summary():
    """Print a summary of all known objects."""
    summary.print_(summary.summarize(muppy.get_objects()))


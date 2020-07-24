"""Miscellaneous utility functions
"""

# Author: David A. Thompson

import os
import os.path

# configure logging
import logging
# define the generic logger
lg=logging


#
# files, directories, paths, executables, ...

# see http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
# Python 3.3 offers shutil.which()
def which(program):
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

# since we're not in python 3, define a uniform approach to testing for existence of a file
def assert_file_exists_p(path):
    if file_exists_p(path):
        return True
    else:
        raise AssertionError("file " + path + " does not exist")

def file_exists_p(path):
    return os.path.isfile(path)

#
# types

# type is a type object
def typeP (x,type):
    if type(x)==type:
        return True
    else:
        return False

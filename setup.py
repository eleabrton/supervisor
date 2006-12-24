
__revision__ = '$Id$'

import sys
import string
version, extra = string.split(sys.version, ' ', 1)
maj, minor = string.split(version, '.', 1)

if not maj[0] >= '2' and minor[0] >= '3':
    msg = ("supervisor requires Python 2.3 or better, you are attempting to "
           "install it using version %s.  Please install with a "
           "supported version" % version)

from distutils.core import setup

setup(
    name = 'supervisor',
    version = "2.0",
    description = ".",
    author = "Chris McDonough",
    author_email = "chrism@plope.com",
    maintainer = "Chris McDonough",
    maintainer_email = "chrism@plope.com",
    scripts=['supervisord', 'supervisorctl'],
    packages = ['supervisor', 'supervisor.medusa', 'supervisor.meld3',
                'supervisor.meld3.elementtree'],
    package_dir = {'supervisor':'.'},
    package_data= {'supervisor':['ui/*.gif', 'ui/*.css', 'ui/*.html']},
    )

#!/usr/bin/env python

{warning}

from setuptools import setup, find_packages, Extension

# Dirty workaround for "error: byte-compiling is disabled." message
import sys
sys.dont_write_bytecode = False

setup(
	name = 'fgc',
	version = '{version}',
	author = 'Mike Kazantsev',
	author_email = 'mike_kazantsev@fraggod.net',
	description = 'Misc stdlib extensions',
	license = 'BSD',
	keywords = 'generic utility misc wrappers extension convenience',
	url = 'http://fraggod.net/oss/fgc',
	packages = find_packages(),
	include_package_data=True,
	long_description = 'Miscellaneous tools to soften stdlib shortcomings'\
		' and inconveniences. Legacy stuff, mostly.'\
		' Not really intended to be used by someone else but author.',
	classifiers = [
		'Development Status :: Eternal Alpha',
		'Topic :: Utilities',
		'License :: OSI Approved :: BSD License' ],
	ext_modules  = [
		Extension(name='fgc.os_ext', sources=['os_ext.c']),
		Extension(name='fgc.psctl', sources=['psctl.c'], include_dirs=['/usr/src/linux/include']),
		Extension(name='fgc.strcaps', sources=['strcaps.c'], libraries=['cap']),
		Extension(name='fgc.stracl', sources=['stracl.c'], libraries=['acl']) ] )

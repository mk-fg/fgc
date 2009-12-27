#!/usr/bin/env python

{warning}

from setuptools import setup, find_packages, Extension

setup(
	name = 'fgc',
	version = '{version}',
	author = 'Mike Kazantsev',
	author_email = 'mike_kazantsev@fraggod.net',
	description = ( 'Miscellaneous tools to soften stdlib shortcomings'
		' and inconveniences. Not really intended to be used by someone else but author.' ),
	license = 'BSD',
	keywords = 'swiss utility misc wrappers extension convenience',
	url = 'http://fraggod.net/oss/fgc',
	packages = find_packages(),
	include_package_data=True,
	long_description = 'Not really ;)',
	# install_requires=['pyyaml'], not really ;)
	classifiers = [
		'Development Status :: Eternal Alpha',
		'Topic :: Utilities',
		'License :: OSI Approved :: BSD License' ],
	ext_modules  = [
		Extension(name='fgc.psctl', sources=['psctl.c'], include_dirs=['/usr/src/linux/include']),
		Extension(name='fgc.strcaps', sources=['strcaps.c'], libraries=['cap']) ] )

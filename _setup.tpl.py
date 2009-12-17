#!/usr/bin/env python

{warning}

from setuptools import setup

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
	packages = ['fgc'],
	long_description = 'Not really ;)',
	classifiers = [
		'Development Status :: Eternal Alpha',
		'Topic :: Utilities',
		'License :: OSI Approved :: BSD License' ] )

'''
git - git-related supplementary functions.

Used by git_wrapper.
Split from git_wrapper into this module, for separate maintaining.

by Mike Kazantsev, 24.10.2008
'''

from subprocess import Popen, PIPE
from string import whitespace as spaces
from glob import glob
import logging as log
import os, sys, re, pkg


class Cfg(file):
	'File_class wrapper to adapt gitconfig to ini-file format by stripping whitespaces'
	def readline(self):
		return file.readline(self).strip(spaces)
	def readlines(self):
		return [line.strip(spaces) for line in file.readlines(self)]
	def write(self, data):
		raise NotImplementedError('Write to gitconfig is not implemented yet')
	def get(self):
		'''Returns ConfigParser wrapper of current class'''
		from ConfigParser import ConfigParser
		cfg_git = ConfigParser()
		cfg_git.readfp(self)
		return cfg_git


def merge():
	'''Interactive merge operation'''
	conflicts = []
	git = exc([pkg.cfg['bin']['git']]+sys.argv[1:], stdout=PIPE, stderr=PIPE)
	rec = re.compile('conflict in (.*)')
	for line in git.stdout:
		line = line.strip(spaces)
		log.info(line)
		if line.startswith('CONFLICT'):
			file = rec.search(line)
			if file: file = file.groups(1)[0]
			else: continue
			rot = exc([pkg.cfg['bin']['git'], 'mergetool', file], stderr=sys.stderr, stdin=PIPE)
			rot.stdin.write('\n') # interactive merge must die :E
			rot.wait()
			conflicts.append(file)
			file += '.orig'
			if os.path.exists(file): os.unlink(file)
	updates = []
	for file in conflicts:
		updates += [
			os.path.abspath(rel).replace("'", "'\\''")
			for rel in glob( os.path.join(os.path.dirname(file), '._upd??_'+os.path.basename(file)) )
		]
	for line in git.stderr: log.error(line)
	if updates: return os.system( pkg.cfg['bin']['decay'] + " -- '"+"' '".join(updates)+"'" )


def clone():
	git = exc([cfg['bin']['git']]+sys.argv[1:], stdout=PIPE, stderr=PIPE)
	for line in git.stdout:
		if line.startswith('Initialized'):
			git_dir = re.search('repository in (.*)', line)
			if git_dir: git_dir = git_dir.groups(1)[0]
			os.chdir(git_dir.rstrip('.git/'))
	for line in git.stderr: log.error(line)
	perm_apply()


def ls_files(sort=True):
	files = exc([pkg.cfg['bin']['git'], 'ls-files', '--full-name'], stdout=PIPE, stderr=sys.stderr).stdout.readlines()
	if sort: files.sort()
	return files


def perm_gen():
	pre_exists = os.path.isfile(pkg.cfg['ownage']['file'])
	pkg.perm_gen(files=ls_files())
	if not pre_exists and os.path.isfile(pkg.cfg['ownage']['file']):
		# Delay is necessary for any further high-level ops on repository
		try: return exc([pkg.cfg['bin']['git'], 'add', pkg.cfg['ownage']['file']]).wait()
		except OSError, err:
			if err.errno != 10: raise err


def exc(*argz, **kwz):
	'''Git commands execution wrapper'''
	if not argz and not kwz:
		try: return pkg.exc([pkg.cfg['bin']['git']] + sys.argv[1:], passthru=True)
		except IndexError: return pkg.exc(pkg.cfg['bin']['git'], passthru=True)
	else: return pkg.exc(*argz, **kwz)

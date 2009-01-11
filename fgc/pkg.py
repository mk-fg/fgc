'''
pkg - package management utility functions.

Used by administrative synchronization tools like git_wrapper and pkg_deploy.
Split from git_wrapper and it's 'git' module, to  be shared w/ pkg_deploy.

by Mike Kazantsev, 01.11.2008
'''

from subprocess import Popen, PIPE
from string import whitespace as spaces
import logging as log
import os, sys, re, sh

# Swallow '--config-dir' parameter
try:
	arg_idx = sys.argv.index('--config-dir')
	del sys.argv[arg_idx]
	cfg_dir = sys.argv[arg_idx]
	del sys.argv[arg_idx], arg_idx
except (IndexError, ValueError): cfg_dir = '/.cFG/cfgit'

# Shared configuration
import yaml
try: cfg = yaml.load(open(os.path.join(cfg_dir, 'config.yaml')).read())
except Exception, ex:
	log.error('Fatal configuration error:\n%s (%s)'%(ex, ex.__doc__))
	sys.exit(1)


def perm_gen(files=[]):
	'''Permissions' information file ('path uid:gid\n' format) generator'''
	numeric = cfg['ownage']['use_ids']
	if cfg['ownage']['omit']:
		log.warn('Omit permissions flag is set, skipping FS metadata changes')
		return
	ownage = {}
	errz = False
	for path in files:
		path = path.strip(spaces)
		if path == cfg['ownage']['file']: continue
		path = path.split(os.sep)
		while 1:
			if path[0] not in ownage:
				try:
					fstat = os.lstat(path[0])
					ownage[path[0]] = '%s:%s:%s'%(
						fstat.st_uid if numeric else sh.uname(fstat.st_uid),
						fstat.st_gid if numeric else sh.gname(fstat.st_gid),
						oct(fstat.st_mode & 07777)
					)
				except OSError:
					log.error('Cannot get owner info for path %s'%path[0])
					errz = True
			if len(path) == 1: break
			path[0] = os.path.join(path[0], path.pop(1))
	if ownage:
		ownage = '\n'.join(sorted(['%s %s'%(path, own) for path,own in ownage.iteritems()]))+'\n'
		try:
			if open(cfg['ownage']['file']).read() != ownage: raise IOError
		except IOError:
			open(cfg['ownage']['file'], 'w').write(ownage)
			os.chmod(cfg['ownage']['file'], int(oct(cfg['ownage']['mode']), 8))
			log.info('Updated ownership information')
	else: log.info('No files given to harvest ownership info')
	if errz:
		log.warn('Execution halted because of errors, send \\n or break it.')
		sys.stdin.readline()

def perm_apply():
	'''Permissions setter, handles ownership information with both numeric and alpha uids/gids'''
	if cfg['ownage']['omit']:
		log.warn('Omit permissions flag is set, skipping FS metadata changes')
		return
	if not os.path.lexists(cfg['ownage']['file']):
		log.warn('No ownership info stored')
		return
	log.info('Setting ownership...')
	errz = False
	try: os.chmod(cfg['ownage']['file'], int(oct(cfg['ownage']['mode']), 8))
	except OSError: log.error('Unable to change mode for %s file'%cfg['ownage']['file'])
	for line in open(cfg['ownage']['file']):
		path, ownage = line.rsplit(' ', 1)
		try: uid, gid, mode = ownage.split(':', 2)
		except ValueError: uid, gid = ownage.split(':', 1) # Deprecated format w/o mode
		try:
			os.lchown(path, sh.uid(uid), sh.gid(gid))
			os.chmod(path, int(mode, 8))
		except OSError:
			errz = True
			log.error('Unable to set permissions %s for path %s'%(ownage, path))
	if errz:
		log.warn('Execution halted because of errors, send \\n or break it.')
		sys.stdin.readline()


def exc(*argz, **kwz):
	'''Command execution wrapper'''
	try:
		kwz['passthru']
		try: return os.system( esc(argz[0][0], argz[0][1:]) )
		except IndexError:
			try: return os.system( esc(argz[0][0]) )
			except IndexError: return os.system( esc(argz[0]) )
	except KeyError:
		return Popen(*argz, **kwz)
def esc(cmd, argz):
	'''Make shell line from given command and arguments'''
	esc=[]
	for val in argz: esc.append("'%s'"%val.replace("'", "'\\''") if val[0] not in ('"', "'") else val)
	return '%s %s'%(cmd, ' '.join(esc))


class Rollback(list):
	'''Rollback file contents generator for pkg_deploy'''
	def append(self, cmd, *argz):
		return list.append(self, esc(cmd, argz))
	def make(self):
		self.reverse()
		return '#!/bin/sh\n' + '\n'.join(self) + '\n'
	def dump(self, path):
		open(path, 'w').write(self.make())
		os.chmod(path, 0755)

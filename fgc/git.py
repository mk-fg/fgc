import itertools as it, operator as op, functools as ft
from string import whitespace as spaces
from fgc import sh, dta, exe
import os, sys, re

import logging
log = logging.getLogger(__name__)


# Swallow '--config-dir' parameter, if any
cfgit = open('/etc/cfgit').read().strip(spaces)
try:
	arg_idx = sys.argv.index('--config-dir')
	del sys.argv[arg_idx]
	cfg_dir = sys.argv[arg_idx]
	del sys.argv[arg_idx], arg_idx
except (IndexError, ValueError): cfg_dir = sh.join(cfgit, 'cfgit')
# Read cfg or die
try: cfg = dta.do(sh.join(cfg_dir, 'config.yaml'))
except Exception as ex:
	log.fatal('Configuration error: %s'%ex)
	sys.exit(1)


from ConfigParser import ConfigParser
class GitCfg(ConfigParser, file):
	'''File_class wrapper to adapt gitconfig to ini-file format by stripping whitespaces'''
	def __init__(self, *argz, **kwz):
		ConfigParser.__init__(self)
		file.__init__(self, *argz, **kwz)
		self.readfp(self)
	def readline(self): return file.readline(self).strip(spaces)
	def readlines(self): return [line.strip(spaces) for line in file.readlines(self)]
	def write(self, data): raise NotImplementedError('Write to gitconfig is not implemented yet')


def update_idx(): exe.proc(cfg.bin.git, 'update-index', '--refresh').wait()


def merge():
	'''Interactive merge operation'''
	conflicts = list()
	git = exc(stdout=exe.PIPE, stderr=exe.PIPE)
	rec = re.compile('conflict in (.*)')
	for line in git.stdout:
		line = line.strip(spaces)
		log.info(line)
		if line.startswith('CONFLICT'):
			file = rec.search(line)
			if file: file = file.groups(1)[0]
			else: continue
			rot = exc((cfg.bin.git, 'mergetool', file), stderr=sys.stderr, stdin=exe.PIPE)
			rot.stdin.write('\n') # interactive merge must die :E
			rot.wait()
			conflicts.append(file)
			file += '.orig'
			if os.path.exists(file): os.unlink(file)
	updates = []
	for file in conflicts:
		updates += list(
			os.path.abspath(rel).replace("'", "'\\''")
			for rel in sh.glob(sh.join(
				os.path.dirname(file), '._upd??_'+os.path.basename(file) )) )
	for line in git.stderr: log.error(line)
	if updates: return exe.proc(*data.chain(cfg.bin.decay, '--', updates)).wait_cli()


def clone():
	git = exc(stdout=exe.PIPE, stderr=exe.PIPE)
	for line in git.stdout:
		if line.startswith('Initialized'):
			git_dir = re.search('repository in (.*)', line)
			if git_dir: git_dir = git_dir.groups(1)[0]
			os.chdir(git_dir.rstrip('.git/'))
	for line in git.stderr: log.error(line)
	perm_apply()


from time import sleep

def ls_files(sort=True):
	files = None
	while True: # aw, fuck it! (dirty hack for nasty bug)
		files = exe.pipe(cfg.bin.git, 'ls-files', '--full-name').stdout.readlines()
		if files: break
		else: sleep(0.1)
	return sorted(files) if sort else files


def exc(*argz, **kwz):
	if not argz:
		argz = list(dta.overlap([cfg.bin.git], sys.argv))
		if not kwz: return exe.proc(*argz).wait_cli()
	return exe.proc(*argz, **kwz)


from fgc import strcaps, acl

def perm_gen():
	'''Permissions information file generator.
	Format: path uid:gid[:mode] [ /cap;cap;... [ /acl,acl,... ] ]\n'''
	numeric = cfg.ownage.use_ids
	if cfg.ownage.omit:
		return log.warn('Omit_permissions flag is set, skipping FS metadata changes')
	ownage = dict()

	for path in ls_files():
		path = path.strip(spaces)
		if path == cfg.ownage.file: continue
		path = path.split(os.sep)

		while True: # try to add every component of the path
			pathc = path[0]
			if pathc not in ownage:
				try: fstat = os.lstat(pathc)
				except OSError: log.error('Unable to stat path: %s'%pathc)
				else:
					ownage[pathc] = '%s:%s:%%s'%( # mode is acl-dependant
						fstat.st_uid if numeric else sh.uname(fstat.st_uid),
						fstat.st_gid if numeric else sh.gname(fstat.st_gid) )
					try: caps = strcaps.get_file(pathc)
					except OSError: caps = None # no kernel/fs support
					try:
						acls = acl.get(pathc)
						if acl.is_mode(acls): raise OSError # just a mode reflection
					except OSError: acls = None # no kernel/fs support
					if caps: ownage[pathc] += '/%s'%caps.replace(' ', ';')
					elif acls: ownage[pathc] += '/'
					if acls:
						mode = acl.get_mode(acls) | (fstat.st_mode & 07000)
						ownage[pathc] += '/%s'%','.join(acls)
					else: mode = fstat.st_mode
					ownage[pathc] %= oct(mode & 07777).lstrip('0')
			if len(path) == 1: break # no more components
			path[0] = sh.join(pathc, path.pop(1))

	if ownage:
		ownage = ''.join( '%s %s\n'%(path, own) for path,own in
			sorted(ownage.iteritems(), key=op.itemgetter(0)) ) + '\n'
		try: old_ownage = open(cfg.ownage.file).read()
		except IOError: old_ownage = None
		if old_ownage != ownage:
			open(cfg.ownage.file, 'w').write(ownage)
			sh.chmod(cfg.ownage.file, int(oct(cfg.ownage.mode), 8))
			log.info('Updated ownership information')
		if old_ownage is None: exe.proc(cfg.bin.git, 'add', cfg.ownage.file).wait()

	else: log.info('No files to harvest ownership info from')

def perm_apply():
	'''Permissions setter, handles ownership information with both numeric and alpha uids/gids'''
	if cfg.ownage.omit: return log.warn('Omit permissions flag is set, skipping FS metadata changes')
	if not os.path.lexists(cfg.ownage.file): return log.warn('No ownership info stored')
	log.info('Setting ownership...')
	skip_flag = False
	try: sh.chmod(cfg.ownage.file, int(oct(cfg.ownage.mode), 8))
	except OSError: log.error('Unable to change mode for %s file'%cfg.ownage.file)
	for ln, line in enumerate(it.ifilter(
			None, (line.strip(spaces) for line in open(cfg.ownage.file)) )):
		if line.startswith('>>>>>>>'):
			skip_flag = False
			continue
		elif line.startswith('<<<<<<<'):
			skip_flag = True
			log.error('Git-merge block detected on line %s'%ln)
		if skip_flag: continue # git-merge block

		path, base = line.rsplit(' ', 1)
		caps = acls = None
		try:
			base, caps = base.split('/', 1)
			caps, acls = caps.split('/', 1)
		except ValueError: pass
		uid, gid, mode = base.split(':')
		mode = sh.mode(mode)

		try:
			try: sh.chown(path, uid, gid, resolve=True)
			except KeyError:
				log.error('No such id - %s:%s (%s)'%(uid,gid,path))
			sh.chmod(path, mode, dereference=False)
		except OSError:
			log.error('Unable to set permissions %s for path %s'%(base, path))
		if acls:
			try: acl.rebase(acls, path, base=mode)
			except OSError:
				log.warn('Unable to set posix ACL %r for path %s'%(acls, path))
		if caps:
			try: strcaps.set_file(caps.replace(';', ' '), path)
			except OSError:
				log.warn('Unable to set posix caps %r for path %s'%(caps, path))


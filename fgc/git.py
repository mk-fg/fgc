from string import whitespace as spaces
from fgc import log, sh, dta, exe
import itertools as it, operator as op, functools as ft
import os, sys, re


# Swallow '--config-dir' parameter, if any
cfgit = open('/etc/cfgit').read().strip(spaces)
try:
	arg_idx = sys.argv.index('--config-dir')
	del sys.argv[arg_idx]
	cfg_dir = sys.argv[arg_idx]
	del sys.argv[arg_idx], arg_idx
except (IndexError, ValueError): cfg_dir = os.path.join(cfgit, 'cfgit')
# Read cfg or die
try: cfg = dta.do(os.path.join(cfg_dir, 'config.yaml'))
except Exception as ex: log.fatal('Configuration error: %s'%ex, crash=1)


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


def update_idx(): exe.add((cfg.bin.git, 'update-index', '--refresh'), block=True)


def merge():
	'''Interactive merge operation'''
	conflicts = []
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
		updates += [
			os.path.abspath(rel).replace("'", "'\\''")
			for rel in sh.glob( os.path.join(os.path.dirname(file), '._upd??_'+os.path.basename(file)) )
		]
	for line in git.stderr: log.error(line)
	if updates: return exe.add(tuple(data.chain(cfg.bin.decay, '--', updates)), sys=True)


def clone():
	git = exc(stdout=exe.PIPE, stderr=exe.PIPE)
	for line in git.stdout:
		if line.startswith('Initialized'):
			git_dir = re.search('repository in (.*)', line)
			if git_dir: git_dir = git_dir.groups(1)[0]
			os.chdir(git_dir.rstrip('.git/'))
	for line in git.stderr: log.error(line)
	perm_apply()


def ls_files(sort=True):
	files = None
	while not files: # aw, fuck it! (dirty hack for nasty bug)
		files = exe.pipe((cfg.bin.git, 'ls-files', '--full-name')).stdout.readlines()
	return sorted(files) if sort else files


def exc(*argz, **kwz):
	if not argz:
		argz = [list(dta.overlap([cfg.bin.git], sys.argv))]
		if not kwz: return exe.add(*argz, sys=True)
	return exe.proc(*argz, **kwz)


def perm_gen():
	'''Permissions' information file ('path uid:gid\n' format) generator'''
	numeric = cfg.ownage.use_ids
	if cfg.ownage.omit: return log.warn('Omit permissions flag is set, skipping FS metadata changes')
	ownage = {}
	errz = False
	for path in ls_files():
		path = path.strip(spaces)
		if path == cfg.ownage.file: continue
		path = path.split(os.sep)
		while True:
			if path[0] not in ownage:
				try:
					fstat = os.lstat(path[0])
					ownage[path[0]] = '%s:%s:%s'%(
						fstat.st_uid if numeric else sh.uname(fstat.st_uid),
						fstat.st_gid if numeric else sh.gname(fstat.st_gid),
						oct(fstat.st_mode & 07777) # can produce likes of 04755
					)
				except OSError:
					log.error('Unable to stat path: %s'%path[0])
					errz = True
			if len(path) == 1: break
			path[0] = os.path.join(path[0], path.pop(1))
	if ownage:
		ownage = ''.join( '%s %s\n'%(path, own) for path,own in
			sorted(ownage.iteritems(), key=op.itemgetter(0)) )
		try: old_ownage = open(cfg.ownage.file).read()
		except IOError: old_ownage = None
		if old_ownage != ownage:
			open(cfg.ownage.file, 'w').write(ownage)
			os.chmod(cfg.ownage.file, int(oct(cfg.ownage.mode), 8))
			log.info('Updated ownership information')
		if old_ownage is None: exe.add((cfg.bin.git, 'add', cfg.ownage.file), block=True)
	else: log.info('No files given to harvest ownership info')
	if errz:
		log.warn('Execution halted because of errors, send \\n or break it.')
		sys.stdin.readline()

def perm_apply():
	'''Permissions setter, handles ownership information with both numeric and alpha uids/gids'''
	if cfg.ownage.omit: return log.warn('Omit permissions flag is set, skipping FS metadata changes')
	if not os.path.lexists(cfg.ownage.file): return log.warn('No ownership info stored')
	log.info('Setting ownership...')
	errz = False
	try: os.chmod(cfg.ownage.file, int(oct(cfg.ownage.mode), 8))
	except OSError: log.error('Unable to change mode for %s file'%cfg.ownage.file)
	for line in open(cfg.ownage.file):
		path, ownage = line.rsplit(' ', 1)
		try: uid, gid, mode = ownage.split(':', 2)
		except ValueError: uid, gid = ownage.split(':', 1) # Deprecated format w/o mode
		try:
			try: os.lchown(path, sh.uid(uid), sh.gid(gid))
			except KeyError:
				log.error('No such id - %s:%s (%s)'%(uid,gid,path))
				errz = True
			try: os.lchmod(path, int(mode, 8)) # py2.6+ only
			except AttributeError:
				if not os.path.islink(path): os.chmod(path, int(mode, 8))
		except OSError:
			errz = True
			log.error('Unable to set permissions %s for path %s'%(ownage, path))
	if errz:
		log.warn('Execution halted because of errors, send \\n or break it.')
		sys.stdin.readline()

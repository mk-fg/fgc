'''
Enhanced clone of standard py module "shutil".

Adds owner/group transferring functionality and some other params.
Optimized and simplified a lot, since original implementation was rubbish.
'''

import os, sys, stat, re, pwd, grp
from os.path import abspath
from fgc import log



class Error(EnvironmentError):
	'''Something went wrong'''


def getids(user):
	try:
		id = int(user)
		return (id, id)
	except ValueError:
		uid = pwd.getpwnam(user).pw_uid
		gid = grp.getgrnam(user).gr_gid
		return (uid, gid)
def uid(user):
	try: return int(user)
	except ValueError: return pwd.getpwnam(user).pw_uid
def gid(group):
	try: return int(group)
	except ValueError: return grp.getgrnam(group).gr_gid
def uname(uid):
	try: return pwd.getpwuid(uid).pw_name
	except KeyError: return uid
def gname(gid):
	try: return grp.getgrgid(gid).gr_name
	except KeyError: return gid
def mode(mode):
	if mode.isdigit():
		if len(mode) < 4: mode = '0'+mode
		while len(mode) < 4: mode += '0'
		return int(mode, 8)
	elif len(mode) == 9:
		val = 0
		bits = (
			0400, # r-- --- ---
			0200, # -w- --- ---
			0100, # --x --- ---
			0040, # --- r-- ---
			0020, # --- -w- ---
			0010, # --- --x ---
			0004, # --- --- r--
			0002, # --- --- -w-
			0001 # --- --- --x
		)
		for n in xrange(len(bits)):
			if mode[n] != '-': val |= bits[n]
		return val
	else:
		raise Error, 'Unrecognized file system mode format: %s'%mode


def chown(path, uid=-1, gid=-1, deference=True):
	if deference: os.chown(path, uid, gid)
	else: os.lchown(path, uid, gid)
def chmod(path, mode, deference=True):
	if deference: os.chmod(path, mode)
	else: os.lchmod(path, mode)


def cat(fsrc, fdst, length=16*1024, recode=None):
	'''copy data from file-like object fsrc to file-like object fdst'''
	while 1:
		buf = fsrc.read(length)
		if not buf: break
		if recode:
			from fgc.enc import recode as rec
			rec(fsrc, fdst, recode)
		else: fdst.write(buf)


def _cmp(src, dst):
	if not os.path.isdir(src):
		try: return os.path.samefile(src, dst)
		except OSError: return False
	else:
		return (os.path.normcase(os.path.abspath(src)) ==
			os.path.normcase(os.path.abspath(dst)))


def cp_cat(src, dst, recode=None, append=False):
	'''Copy data from src to dst'''
	if _cmp(src, dst): raise Error, "'%s' and '%s' are the same file" %(src,dst)
	fsrc = None
	fdst = None
	try:
		fsrc = open(src, 'rb')
		fdst = open(dst, 'wb' if not append else 'ab')
		cat(fsrc, fdst, recode=recode)
	except IOError, err: raise Error, str(err)
	finally:
		if fdst: fdst.close()
		if fsrc: fsrc.close()


def cp(src, dst, attrz=False):
	'''Copy data and mode bits ("cp src dst"). The destination may be a dir.'''
	if os.path.isdir(dst): dst = os.path.join(dst, os.path.basename(src))
	cp_cat(src, dst)
	cp_stat(src, dst, attrz=attrz)


def cp_stat(src, dst, attrz=False, deference=True):
	'''Copy mode or full attrz (atime, mtime and ownership) from src to dst'''
	if deference:
		chmod = os.chmod
		chown = os.chown
		st = os.stat(src)
	else:
		st = os.lstat(src)
		try:
			chmod = os.lchmod # Py 2.6 only
		except AttributeError:
			if os.path.islink(dst):
				chmod = lambda dst,mode: True # Don't change any modes
			else: chmod = os.chmod
		chown = os.lchown
	chmod(dst, stat.S_IMODE(st.st_mode))
	if attrz:
		if deference: os.utime(dst, (st.st_atime, st.st_mtime))
		chown(dst, st.st_uid, st.st_gid)


cp_p = lambda src,dst: cp(src, dst, attrz=True)


def cp_d(src, dst, symlinks=False, attrz=False):
	'''Copy only one node, whatever it is.'''
	if symlinks and os.path.islink(src):
		src_node = os.readlink(src)
		os.symlink(src_node, dst)
	elif os.path.isdir(src):
		try: os.makedirs(dst)
		except OSError, err: raise Error, str(err)
	else: cp(src, dst, attrz=attrz)
	cp_stat(src, dst, attrz=attrz)
	# TODO: What about devices, sockets etc.?


def cp_r(src, dst, symlinks=False, attrz=False, skip=[], onerror=None, atom=cp_d):
	'''
	Recursively copy a directory tree, preserving mode/stats.

	The destination directory must not already exist.
	If exception(s) occur, an Error is raised with a list of reasons.
	If onerror is passed, it'll be called on every raised exception.
	'skip' pattern(s) will be skipped.

	If the optional symlinks flag is true, symbolic links in the
	source tree result in symbolic links in the destination tree; if
	it is false, the contents of the files pointed to by symbolic
	links are copied.

	Atom argument should be a callable, to be called in the same
	way as cp_d function to transfer each individual file.
	'''
	try: skip = [re.compile(skip)]
	except TypeError: skip = [re.compile(pat) for pat in skip]
	atom(src, dst, attrz=attrz)
	if not onerror:
		errors = []
		onerror = lambda *args: errors.append(args)
	for entity in crawl(src, dirs=True, topdown=True, onerror=onerror):
		for pat in skip:
			if pat.match(entity): break
		else:
			try:
				src_node = os.path.join(src, entity)
				dst_node = os.path.join(dst, entity)
				atom(src_node, dst_node, symlinks=symlinks, attrz=attrz)
			except (IOError, OSError, Error), err: onerror(src_node, dst_node, str(err))
	try:
		if errors: raise Error, errors
	except NameError: pass


def rm(path, onerror=None):
	'''
	Remove path.

	If exception(s) occur, an Error is raised with original error.
	If onerror is passed, it'll be called on exception.
	'''
	try: mode = os.lstat(path).st_mode
	except OSError: mode = 0
	try:
		if stat.S_ISDIR(mode): os.rmdir(path)
		else: os.remove(path)
	except OSError, err:
		if onerror: onerror(path, err)
		elif onerror != False: raise Error, err


def rr(path, onerror=None, preserve=[], keep_root=False):
	'''
	Recursively remove path.

	If exception(s) occur, an Error is raised with original error.
	If onerror is passed, it'll be called on every raised exception.
	'preserve' pattern(s) will be skipped.

	Also includes original path preservation flag.
	'''
	try: preserve = [re.compile(preserve)]
	except TypeError: preserve = [re.compile(pat) for pat in preserve]
	for entity in crawl(path, dirs=True, topdown=False, onerror=onerror):
		for pat in preserve:
			if pat.match(entity): break
		else:
			try: rm(os.path.join(path, entity))
			except Error, err:
				if not (preserve and os.path.isdir(path)): # Quite possible, but not 100%
					if not onerror: raise
					else: onerror(err)
	if not (preserve or keep_root): rm(path, onerror)


def mv(src, dst):
	'''
	Recursively move a path.

	If the destination is on our current filesystem, then simply use
	rename.  Otherwise, copy src to the dst and then remove src.
	A lot more could be done here...  A look at a mv.c shows a lot of
	the issues this implementation glosses over.
	'''
	try: os.rename(src, dst)
	except OSError:
		if _cmp(src, dst): raise Error, "'%s' and '%s' are the same object."%(src,dst)
		cp_r(src, dst, symlinks=True, attrz=True)
		rr(src)


def crawl(top, filter=None, exclude=None, dirs=True, topdown=True, onerror=False):
	'''Filesystem nodes iterator.'''
	nodes = []
	try: filter = filter and [re.compile(filter)]
	except TypeError: filter = [re.compile(regex) for regex in filter]
	try: exclude = exclude and [re.compile(exclude)]
	except TypeError: exclude = [re.compile(regex) for regex in exclude]
	for root, d, f in os.walk(top, topdown=topdown):
		root = root[len(top):].lstrip('/')
		if dirs: f = d + f # dirs first
		for name in f:
			path = os.path.join(root, name)
			if exclude:
				for regex in exclude:
					match = regex.search(path)
					if match: break
				else: match = None
				if match:
					if onerror: onerror(crawl, path, sys.exc_info())
					continue
			if filter:
				for regex in filter:
					if regex.search(path): break
				else:
					if onerror: onerror(crawl, path, sys.exc_info())
					continue
			yield os.path.join(root, name)


def touch(path, mode=0644, uid=None, gid=None):
	'''Create or truncate a file with given stats.'''
	open(path, 'wb')
	os.chmod(path, mode)
	if uid or gid:
		if not uid: uid = -1
		if not gid: gid = -1
		os.chown(path, uid, gid)


def mkdir(path, mode=0755, uid=None, gid=None, recursive=False):
	'''Create a dir with given stats.'''
	ppath = path
	if recursive:
		stack = []
		while ppath and not os.path.isdir(ppath):
			stack.insert(0, ppath)
			ppath = os.path.dirname(ppath)
	else: stack = [path]
	for ppath in stack:
		try:
			os.mkdir(ppath, mode)
			if uid != None or gid != None:
				if uid == None: uid = -1
				if gid == None: gid = -1
				os.chown(ppath, uid, gid)
		except OSError, err: raise Error, err


def ln(src, dst, hard=False, recursive=False):
	'''Create a link'''
	if recursive:
		lnk_dir = os.path.dirname(dst)
		if not os.path.exists(lnk_dir): mkdir(lnk_dir, recursive=recursive)
	try:
		if not hard: os.symlink(src, dst)
		else: os.link(src, dst)
	except OSError, err: raise Error, err


import itertools as it, operator as op, functools as ft
from glob import iglob
_glob_cbex = re.compile(r'\{[^}]+\}')
def glob(pattern):
	'''Globbing with braces expansion'''
	subs = list()
	while True:
		ex = _glob_cbex.search(pattern)
		if not ex: break
		subs.append(ex.group(0)[1:-1].split(','))
		pattern = pattern[:ex.span()[0]] + '%s' + pattern[ex.span()[1]:]
	return it.chain.from_iterable( iglob(pattern%combo) for combo in product(*subs) ) if subs else iglob(pattern)


def df(path):
	'''Get (size, available) disk space, bytes'''
	df = os.statvfs(path)
	return (df.f_blocks * df.f_bsize, df.f_bavail * df.f_bsize)


from tempfile import mkstemp
def mktemp(path):
	'''Helper function to return tmp fhandle and callback to move it into a given place'''
	tmp_path, tmp = os.path.split(path)
	tmp_path = mkstemp(prefix=tmp+os.extsep, dir=tmp_path)[1]
	commit = lambda: mv(tmp_path, path)
	return open(tmp_path, 'w'), commit



from time import sleep
import fcntl

class LockError(EnvironmentError):
	'''Inability to acquire lock'''

class flock(object):
	'''Filesystem lock'''
	__slots__ = ('locked', '_lock', '_type', '_del')
	def __init__(self, path, make=False, shared=False, remove=None):
		self.locked = self._del = False
		if remove == None: remove = make
		try: self._lock = open(path)
		except (IOError,OSError), err:
			if make:
				touch(path)
				self._lock = open(path)
			else: raise Error, err
		if remove: self._del = path
		self._type = fcntl.LOCK_EX if not shared else fcntl.LOCK_SH
	def check(self, grab=False):
		if self.locked: return self.locked
		try: fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
		except IOError as ex:
			if not grab: return False
			else: return None # checked internally
		else:
			if grab: return self
			else:
				fcntl.flock(self._lock, fcntl.LOCK_UN)
				return False
	def acquire(self, timeout=None, interval=5):
		if not self.locked:
			if not timeout:
				fcntl.flock(self._lock, fcntl.LOCK_EX)
				self.locked = True
				return self
			else:
				for attempt in xrange(0, timeout, interval):
					attempt = self.check(True)
					if attempt:
						self.locked = True
						return self
					else:
						log.debug('Waiting for lock: %s'%self._lock)
						sleep(interval)
				else: raise LockError('Unable to acquire lock: %s'%self._lock)
	def release(self):
		if self.locked:
			fcntl.flock(self._lock, fcntl.LOCK_UN)
			self.locked = False
		return self
	def __del__(self):
		self.release()
		if self._del: rm(self._del)
	__str__ = __repr__ = lambda s: '<FileLock %s>'%s._lock
	def __enter__(self): return self.acquire()
	def __exit__(self, ex_type, ex_val, ex_trace): self.release()

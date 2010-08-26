'''
Enhanced clone of standard py module "shutil".

Adds owner/group transferring functionality and some other params.
Optimized and simplified a lot, since original implementation was rubbish.
'''

import os, sys, stat, re, pwd, grp
from os.path import join, islink
from os import walk, rmdir
import log, warnings



class Error(EnvironmentError):
	'''Something went wrong'''


def getids(user): return uid(user), gid(user)
def resolve_ids(tuid=-1, tgid=-1):
	if tuid != -1 and tgid == -1 and ':' in tuid: # user:group spec
		tuid, tgid = tuid.split(':')
	return uid(tuid), gid(tgid)

def uid(user):
	try: return int(user)
	except ValueError:
		return pwd.getpwnam(user).pw_uid
def gid(group):
	try: return int(group)
	except ValueError:
		return grp.getgrnam(group).gr_gid
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
			0001 )# --- --- --x
		for n in xrange(len(bits)):
			if mode[n] != '-': val |= bits[n]
		return val
	else:
		raise Error, 'Unrecognized file system mode format: %s'%mode


def chown(path, tuid=-1, tgid=-1,
		recursive=False, dereference=True, resolve=False):
	if resolve: tuid, tgid = resolve_ids(tuid, tgid)
	op = os.chown if dereference else os.lchown
	if recursive:
		for node in it.imap( ft.partial(join, path),
			crawl(path, dirs=True) ): op(node, tuid, tgid)
	op(path, tuid, tgid)
def chmod(path, bits, dereference=True, merge=False):
	if merge:
		bits = stat.S_IMODE(( os.stat
			if dereference else os.lstat )(path).st_mode) | bits
	if dereference: os.chmod(path, bits)
	else:
		try: os.lchmod(path, bits)
		except AttributeError: # no support for symlink modes
			if not islink(path): os.chmod(path, bits)


def cat(fsrc, fdst, length=16*1024, recode=None, sync=False):
	'''copy data from file-like object fsrc to file-like object fdst'''
	while True:
		buf = fsrc.read(length)
		if not buf: break
		if recode:
			from enc import recode as rec
			rec(src=fsrc, dst_enc=recode, dst=fdst)
		else: fdst.write(buf)
	if sync: fdst.flush()


def _cmp(src, dst):
	if not os.path.isdir(src):
		try: return os.path.samefile(src, dst)
		except OSError: return False
	else:
		return (os.path.normcase(os.path.abspath(src)) ==
			os.path.normcase(os.path.abspath(dst)))


def cp_cat(src, dst, recode=None, append=False, sync=False):
	'''Copy data from src to dst'''
	if _cmp(src, dst): raise Error, "'%s' and '%s' are the same file" %(src,dst)
	fsrc = None
	fdst = None
	try:
		fsrc = open(src, 'rb')
		fdst = open(dst, 'wb' if not append else 'ab')
		cat(fsrc, fdst, recode=recode, sync=sync)
	except IOError, err: raise Error, str(err)
	finally:
		if fdst: fdst.close()
		if fsrc: fsrc.close()


def cp(src, dst, attrz=False, sync=False):
	'''Copy data and mode bits ("cp src dst"). The destination may be a dir.'''
	if os.path.isdir(dst): dst = join(dst, os.path.basename(src))
	cp_cat(src, dst, sync=sync)
	cp_stat(src, dst, attrz=attrz)


def cp_stat(src, dst, attrz=False, dereference=True, skip_ts=False):
	'''Copy mode or full attrz (atime, mtime and ownership) from src to dst'''
	if dereference:
		chmod = os.chmod
		chown = os.chown
		st = os.stat(src) if isinstance(src, (str, unicode)) else src
	else:
		st = os.lstat(src) if isinstance(src, (str, unicode)) else src
		try:
			chmod = os.lchmod # py 2.6 only
		except AttributeError:
			if islink(dst):
				chmod = lambda dst,mode: True # don't change any modes
			else: chmod = os.chmod
		chown = os.lchown
	chmod(dst, stat.S_IMODE(st.st_mode))
	if attrz:
		if dereference and not skip_ts: os.utime(dst, (st.st_atime, st.st_mtime)) # not for symlinks
		chown(dst, st.st_uid, st.st_gid)
	return st


cp_p = lambda src,dst: cp(src, dst, attrz=True)


def cp_d(src, dst, symlinks=False, attrz=False):
	'''Copy only one node, whatever it is.'''
	if symlinks and islink(src):
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
	If onerror is passed, itll be called on every raised exception.
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
				src_node = join(src, entity)
				dst_node = join(dst, entity)
				atom(src_node, dst_node, symlinks=symlinks, attrz=attrz)
			except (IOError, OSError, Error), err: onerror(src_node, dst_node, str(err))
	try:
		if errors: raise Error, errors
	except NameError: pass


def rm(path, onerror=None):
	'''
	Remove path.

	If exception(s) occur, an Error is raised with original error.
	If onerror is passed, itll be called on exception.
	'''
	try: mode = os.lstat(path).st_mode
	except OSError: mode = 0
	try:
		if stat.S_ISDIR(mode): rmdir(path)
		else: os.remove(path)
	except OSError, err:
		if onerror: onerror(path, err)
		elif onerror is not False: raise Error, err


def rr(path, onerror=None, preserve=[], keep_root=False):
	'''
	Recursively remove path.

	If exception(s) occur, an Error is raised with original error.
	If onerror is passed, itll be called on every raised exception.
	'preserve' pattern(s) will be skipped.

	Also includes original path preservation flag.
	'''
	try: preserve = [re.compile(preserve)]
	except TypeError: preserve = [re.compile(pat) for pat in preserve]
	for entity in crawl(path, dirs=True, topdown=False, onerror=onerror):
		for pat in preserve:
			if pat.match(entity): break
		else:
			try: rm(join(path, entity), onerror=onerror)
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


def crawl(top, filter=None, exclude=None,
	dirs=True, topdown=True, onerror=False, dirs_only=False):
	'''Filesystem nodes iterator.'''
	nodes = []
	try: filter = filter and [re.compile(filter)]
	except TypeError: filter = [re.compile(regex) for regex in filter]
	try: exclude = exclude and [re.compile(exclude)]
	except TypeError: exclude = [re.compile(regex) for regex in exclude]
	for root, d, f in walk(top, topdown=topdown):
		root = root[len(top):].lstrip('/')
		if dirs_only: f = d
		elif dirs: f = d + f # dirs first
		for name in f:
			path = join(root, name)
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
			yield path


def touch(path, mode=0644, tuid=-1, tgid=-1, resolve=False):
	'''Create or truncate a file with given stats.'''
	open(path, 'w')
	os.chmod(path, mode)
	chown(path, tuid, tgid, resolve=resolve)


def mkdir(path, mode=0755, tuid=-1, tgid=-1, recursive=False, resolve=False):
	'''Create a dir with given stats.'''
	if resolve: tuid, tgid = resolve_ids(tuid, tgid)
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
			if tuid != -1 or tgid != -1: os.chown(ppath, tuid, tgid)
		except OSError, err: raise Error, err


def ln(src, dst, hard=False, recursive=False):
	'''Create a link'''
	if recursive:
		# Quite confusing flag
		# It means just to create dir in which link should reside
		lnk_dir = os.path.dirname(dst)
		if not os.path.exists(lnk_dir):
			mkdir(lnk_dir, recursive=recursive)
	try:
		if not hard: os.symlink(src, dst)
		else: os.link(src, dst)
	except OSError, err: raise Error, err


from glob import iglob
import itertools as it
_glob_cbex = re.compile(r'\{[^}]+\}')
def glob(pattern):
	'''Globbing with braces expansion'''
	subs = list()
	while True:
		ex = _glob_cbex.search(pattern)
		if not ex: break
		subs.append(ex.group(0)[1:-1].split(','))
		pattern = pattern[:ex.span()[0]] + '%s' + pattern[ex.span()[1]:]
	return it.chain.from_iterable( iglob(pattern%combo) for combo in it.product(*subs) ) if subs else iglob(pattern)


def df(path):
	'''Get (size, available) disk space, bytes'''
	df = os.statvfs(path)
	return (df.f_blocks * df.f_bsize, df.f_bavail * df.f_bsize)


from dta import chain
from collections import deque

class GC:
	'''Garbage Collector object
		Works with:
			callable - run
			iterable - recurse to each element
			file - close
			string - rm path'''
	# TODO: Add weakref option
	__slots__ = ()
	__actz = deque()
	def __init__(self, *actz):
		for act in chain(actz): self.__actz.append(act)
	def __del__(self):
		while self.__actz:
			act = self.__actz.popleft() # destroys reference to object
			try: act() # isinstance of Callable check fails here w/ some weird error
			except TypeError: pass
			else: continue
			if isinstance(act, file): act.close()
			elif isinstance(act, (str, unicode)): rm(act, onerror=False)
			else: log.warn('Unknown garbage type: %r'%act)
	def add(self, *actz):
		for act in actz:
			if not isinstance(act, (str, unicode)):
				try: self.__actz.extend(act)
				except TypeError: self.__actz.append(act)
			else: self.__actz.append(act)
_gc = GC()

def gc(*argz): return _gc.add(*argz)


from tempfile import mkstemp

def mktemp(path, mode=None, tuid=-1, tgid=-1, atomic=False, sync=False):
	'''Helper function to return tmp fhandle and callback to move it into a given place'''
	tmp_path, tmp = os.path.split(path)
	tmp_path = mkstemp(prefix=tmp+os.extsep, dir=tmp_path)[1]
	tmp = open(tmp_path, 'wb+')
	gc(tmp, tmp_path) # to collect leftover
	post_stat = list()
	if mode:
		post_stat.append(ft.partial(chmod, mode=mode))
	if tuid != -1 or tgid != -1:
		post_stat.append(ft.partial(chown, tuid=tuid, tgid=tgid))
	pre_stat = os.path.exists(path) and os.stat(path) # for atomic commits

	def commit(sync=sync, atomic=atomic): # default values from parent function
		tmp_sync, dst_path = False, path # localize vars
		try: tmp.flush() # to ensure that next read gets all data
		except ValueError:
			if not atomic:
				cp_cat(tmp_path, dst_path, sync=sync) # tmp was closed already
				tmp_sync = True # to indicate that we're done with it
		if atomic:
			tmp.close()
			try:
				if not post_stat:
					st = cp_stat(pre_stat or dst_path, tmp_path,
						attrz=True, dereference=True, skip_ts=True) # copy attrz from dst
				else:
					st = pre_stat or os.stat(dst_path)
					while post_stat: post_stat.pop()(tmp_path) # use passed attrz
				if stat.S_ISLNK(st.st_mode): dst_path = os.path.readlink(path)
			except OSError: pass
			mv(tmp_path, dst_path) # atomic for same fs, a bit dirty otherwise
		elif not tmp_sync: # file is still opened
			tmp.seek(0)
			with open(dst_path, 'w') as src:
				cat(tmp, src)
				if sync: src.flush()
			tmp.close()
		if post_stat: # for closed non-atomic or fuckup cases
			while post_stat: post_stat.pop()(dst_path) # set passed attrz
		rm(tmp_path, onerror=False)

	return tmp, commit


from zlib import crc32 as zlib_crc32
import functools as ft
def crc32(stream, bs=8192):
	'''Calculate crc32 of a given stream, which can be specified as a file-like object,
		string or a sequence / iterator of objects, which ll be spliced via data.chain function.
		Note: it may make sense for iterators, but strings can be compared directly.'''
	cs, block = zlib_crc32(''), True
	stream = ft.partial(stream.read, bs) if hasattr(stream, 'read') else (
		iter(stream).next if not isinstance(stream, (str, unicode)) else chain(stream).next )
	while block:
		try: block = stream()
		except StopIteration: block = ''
		cs = zlib_crc32(block, cs)
	return abs(cs)


from time import sleep
import fcntl

class LockError(EnvironmentError):
	'''Inability to acquire lock'''

class Flock(object):
	'''Filesystem lock'''
	gc_unlock = True

	@property
	def _type(self): return fcntl.LOCK_EX if not self._shared else fcntl.LOCK_SH

	def __init__(self, path, make=False, shared=False, remove=None, timeout=None):
		warnings.warn( 'Usage of sh.Flock class is unreliable'
			' and deprecated - use sh.flock2 instead', DeprecationWarning )
		self.locked = self._del = False
		if remove == None: remove = make
		try: self._lock = open(path)
		except (IOError,OSError), err:
			if make:
				touch(path)
				self._lock = open(path)
			else: raise Error, err
		if remove: self._del = path
		self._shared = shared
		if timeout is not None: self.acquire(timeout)

	def check(self, grab=False):
		if self.locked: return self.locked
		try: fcntl.flock(self._lock, self._type | fcntl.LOCK_NB)
		except IOError, ex:
			if not grab: return False
			else: return None # checked internally
		else:
			if grab:
				self.locked = True
				return self
			else:
				fcntl.flock(self._lock, fcntl.LOCK_UN)
				return False

	def acquire(self, timeout=False, interval=5, shared=None, release=False):
		# Lock is not released before re-locking by default:
		#  this way will ensure consistency but WILL
		#  cause deadlock if two scripts will call it on one file.
		# Alternative way is via release arg.
		if not self.locked or shared != self._shared:
			if release and self.locked: self.release() # break consistency, avoid deadlocks
			if not shared is None: self._shared = shared # update lock type for all future calls as well
			if not timeout:
				fcntl.flock(self._lock, self._type)
				self.locked = True
			else:
				for attempt in xrange(0, timeout, int(interval)):
					attempt = self.check(True)
					if attempt: break
					else:
						log.debug('Waiting for lock: %s'%self._lock)
						sleep(interval)
				else: raise LockError('Unable to acquire lock: %s'%self._lock)
		return self

	def release(self, cleanup=True):
		try: fcntl.flock(self._lock, fcntl.LOCK_UN)
		except: pass
		self.locked = False
		if cleanup and self._del: rm(self._del, onerror=False)
		return self

	def __del__(self):
		if self.gc_unlock and self.locked:
			self.release()
			if self._del: rm(self._del, onerror=False)

	__str__ = __repr__ = __hash__ = lambda s: '<FileLock %s>'%s._lock
	def __enter__(self): return self.acquire()
	def __exit__(self, ex_type, ex_val, ex_trace): self.release()

flock = Flock # deprecated legacy alias



from time import time
import signal, errno

def flock2(path, contents=None, add_newline=True, append=False, block=False):
	'Simplier and more reliable flock function'

	try:
		lock = open(path, ('r+' if os.path.exists(path) else 'w') if not append else 'a+')
		if not block: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
		else:
			prev_alarm = signal.alarm(block)
			if prev_alarm: prev_alarm = time() + prev_alarm
			prev_alarm_handler = signal.signal(signal.SIGALRM, lambda sig,frm: None)
			try: fcntl.flock(lock, fcntl.LOCK_EX)
			except (OSError, IOError) as err:
				if err.errno != errno.EINTR: raise
				else: raise LockError('Timeout has passed ({0})'.format(block))
			finally:
				signal.signal(signal.SIGALRM, prev_alarm_handler)
				if prev_alarm:
					prev_alarm = prev_alarm - time()
					if prev_alarm > 0: signal.alarm(prev_alarm)
					else:
						signal.alarm(0)
						os.kill(os.getpid(), signal.SIGALRM)
				else: signal.alarm(0)

	except (IOError, OSError, LockError) as ex:
		raise LockError('Unable to acquire lockfile ({0})): {1}'.format(path, ex))

	if contents:
		if not append:
			lock.seek(0, os.SEEK_SET)
			lock.truncate()
		lock.write(str(contents) + '\n')
		lock.flush()
	return lock



def multi_lock(*paths, **kwz):
	try: timeout = kwz.pop('timeout')
	except: deadline = None
	else: deadline = time() + timeout
	locks = list()
	while True:
		for path in paths:
			if isinstance(path, (tuple, list)):
				path, subkwz = path
				kwz.update(subkwz)
			lock = flock(path, **kwz).check(grab=True)
			if not lock: break
			else: locks.append(lock)
		else: break
		for lock in locks: lock.release()
		if deadline and time() > deadline:
			raise LockError('Unable to acquire locks: %s'%', '.join(it.imap(str, paths)))
		sleep(min(5, deadline-time() if deadline else 5))
	return locks


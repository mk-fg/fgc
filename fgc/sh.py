'''
Enhanced clone of standard py module "shutil".

Adds owner/group transferring functionality and some other params.
Optimized and simplified a lot, since original implementation was rubbish.
'''

import os, sys, stat, re, pwd, grp
from os.path import abspath
import logging as log

__all__ = [
	'uid',
	'cp_cat',
	'cp_p',
	'cp_r',
	'rr',
	'uname',
	'gname',
	'touch',
	'cp',
	'cp_d',
	'grp',
	'mkdir',
	'_cmp',
	'gid',
	'rm',
	'cp_stat',
	'getids',
	'Error',
	'cat',
	'mv',
	'crawl',
	'ln',
	'ln_r'
]



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


def cat(fsrc, fdst, length=16*1024):
	'''copy data from file-like object fsrc to file-like object fdst'''
	while 1:
		buf = fsrc.read(length)
		if not buf: break
		fdst.write(buf)


def _cmp(src, dst):
	if not os.path.isdir(src):
		try: return os.path.samefile(src, dst)
		except OSError: return False
	else:
		return (os.path.normcase(os.path.abspath(src)) ==
			os.path.normcase(os.path.abspath(dst)))


def cp_cat(src, dst):
	'''Copy data from src to dst'''
	if _cmp(src, dst): raise Error, "'%s' and '%s' are the same file" %(src,dst)
	fsrc = None
	fdst = None
	try:
		fsrc = open(src, 'rb')
		fdst = open(dst, 'wb')
		cat(fsrc, fdst)
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
		elif not onerror: raise Error, err


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


def crawl(top, filter=None, dirs=True, topdown=True, onerror=False):
	'''Filesystem nodes iterator.'''
	nodes = []
	try: filter = filter and [re.compile(filter)]
	except TypeError: filter = [re.compile(regex) for regex in filter]
	for root, d, f in os.walk(top, topdown=topdown):
		root = root[len(top):].lstrip('/')
		if dirs: f = d + f # dirs first
		for name in f:
			path = os.path.join(root, name)
			if filter:
				for regex in filter:
					if regex.search(path): break
				else: # No matches
					if onerror == True: log.info('Skipping path "%s" due to filter settings'%path)
					elif onerror: onerror(crawl, path, sys.exc_info())
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
		while not os.path.isdir(ppath):
			stack.insert(0, ppath)
			ppath = os.path.dirname(ppath)
	else: stack = [path]
	for ppath in stack:
		try:
			os.mkdir(ppath, mode)
			if uid or gid:
				if not uid: uid = -1
				if not gid: gid = -1
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


def ln_r(src, dst, skip=[], onerror=None):
	'''Make a hardlink-tree from an existing one.'''
	return cp_r(
		src, dst, skip=skip, onerror=onerror,
		atom=lambda *argz,**kwz: cp_d(*argz, **kwz) if os.path.isdir(argz[0]) else ln(*argz[0:2],hard=True)
	)

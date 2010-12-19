# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function


'My extended version of standard py module "shutil"'


import itertools as it, operator as op, functools as ft

import os, sys, stat, re, pwd, grp, types
from fgc import os_ext
from warnings import warn

# These are also re-exported
from os.path import join, islink, isdir
from os import rmdir
from fgc.os_ext import listdir



class Error(Exception): pass


def resolve_ids(uid=-1, gid=-1):
	if uid is None: uid = -1
	if gid is None: gid = -1
	if isinstance(uid, types.StringTypes) and uid != -1\
		and gid == -1 and ':' in uid: uid, gid = uid.split(':', 1)
	return to_uid(uid), to_gid(gid)

def to_uid(user):
	return user if isinstance(user, int)\
		else pwd.getpwnam(user).pw_uid
def to_gid(group):
	return group if isinstance(group, int)\
		else grp.getgrnam(group).gr_gid

def to_uname(uid):
	try: return pwd.getpwuid(uid).pw_name
	except KeyError: return uid
def to_gname(gid):
	try: return grp.getgrgid(gid).gr_name
	except KeyError: return gid


def chown(path, uid=-1, gid=-1, recursive=False, dereference=True):
	uid, gid = resolve_ids(uid, gid)
	op = os.chown if dereference else os.lchown
	if recursive:
		for node in walk(path): op(node, uid, gid)
	op(path, uid, gid)

def chmod(path, bits, dereference=True, merge=False):
	if merge:
		bits = stat.S_IMODE(( os.stat
			if dereference else os.lstat )(path).st_mode) | bits
	if dereference: os.chmod(path, bits)
	else:
		try: os.lchmod(path, bits)
		except AttributeError: # linux does not support symlink modes
			if dereference or not os.path.islink(path): os.chmod(path, bits)



from shutil import copyfileobj

def cat(fsrc, fdst, bs=16*1024, flush=False, sync=False):
	copyfileobj(fsrc, fdst, bs)
	if flush or sync: fdst.flush()
	if sync: os.fsync(fdst.fileno())


def _cmp(src, dst):
	if not isdir(src):
		try: return os.path.samefile(src, dst)
		except OSError: return False
	else:
		return ( os.path.normcase(os.path.abspath(src))
			== os.path.normcase(os.path.abspath(dst)) )


def cp_data(src, dst, append=False, flush=True, sync=False):
	'Copy data from src to dst'
	if _cmp(src, dst):
		raise Error('{0!r} and {1!r} are the same file'.format(src, dst))
	with open(src, 'rb') as fsrc,\
			open(dst, 'wb' if not append else 'ab') as fdst:
		try: cat(fsrc, fdst, flush=flush, sync=sync)
		except IOError as err: raise Error(err)


def cp_meta(src, dst, attrz=False, dereference=True, skip_ts=None):
	'Copy mode or full attrz (atime, mtime and ownership) from src to dst'
	chmod, chown, st, utime_set = (os.chmod, os.chown, os.stat, os.utime)\
		if dereference else (os.lchmod, os.lchown, os.lstat, os_ext.lutimes)
	st = st(src) if isinstance(src, types.StringTypes) else src
	chmod(dst, stat.S_IMODE(st.st_mode))
	if (attrz if skip_ts is None else not skip_ts): utime_set(dst, (st.st_atime, st.st_mtime))
	if attrz: chown(dst, st.st_uid, st.st_gid)
	return st


def cp(src, dst, attrz=False, dereference=True, flush=False, sync=False, skip_ts=None):
	'Copy data and mode bits ("cp src dst"). The destination may be a dir.'
	if isdir(dst): dst = join(dst, os.path.basename(src))
	src_stat = (os.stat if dereference else os.lstat)(src)
	if not any( f(src_stat.st_mode) for f in
			op.attrgetter('S_ISREG', 'S_ISDIR', 'S_ISLNK')(stat) ):
		raise Error('Node is not a file/dir/link, cp of these is not supported.')
	cp_data(src, dst, flush=flush, sync=sync)
	return cp_meta(src_stat, dst, attrz=attrz, skip_ts=skip_ts)

cp_p = lambda src,dst: cp(src, dst, attrz=True)

def cp_d( src, dst, dereference=True, attrz=False,
		flush=False, sync=False, skip_ts=None ):
	'Copy only one node, whatever it is.'
	if not dereference and islink(src):
		src_node = os.readlink(src)
		os.symlink(src_node, dst)
		return cp_meta( src, dst,
			dereference=False, attrz=attrz, skip_ts=skip_ts )
	elif isdir(src):
		try:
			os.makedir(dst)
			return cp_meta(src, dst, attrz=attrz, skip_ts=skip_ts)
		except OSError as err: raise Error(err)
	else: return cp(src, dst, attrz=attrz, skip_ts=skip_ts)


def cp_r( src, dst, dereference=True,
		attrz=False, onerror=False, atom=cp_d, **crawl_kwz ):
	'''
	Recursively copy a directory tree, preserving mode/stats.

	The destination directory must not already exist.
	If exception(s) occur, an Error is raised with a list of reasons.
	If onerror is passed, it'll be called on every raised exception.
		If it's False (default), exceptions are not raised, but all errors are collected
		and returned as a list with the same tuples as arguments to the callable.
		None will raise Error and halt execution on the first occasion.

	If the optional dereference flag is false, symbolic links in the
	source tree result in symbolic links in the destination tree; if
	it is false, the contents of the files pointed to by symbolic
	links are copied.

	Atom argument should be a callable, to be called in the same
	way as cp_d function to transfer each individual file.
	'''
	skip = [re.compile(skip)] if isinstance( skip,
		types.StringTypes ) else list(re.compile(pat) for pat in skip)
	atom(src, dst, attrz=attrz)

	if onerror is False: errors, onerror = list(), lambda *args: errors.append(args)
	else: errors = None

	for entity in crawl( src, depth=False,
			relative=True, onerror=onerror, **crawl_kwz ):
		try:
			src_node, dst_node = join(src, entity), join(dst, entity)
			atom(src_node, dst_node, dereference=dereference, attrz=attrz)
		except (IOError, OSError, Error) as err:
			if onerror is None: raise Error(err)
			else: onerror(src_node, dst_node, err)

	if errors is not None: return errors


def rm(path, onerror=None):
	'''
	Remove path.

	If exception(s) occur, an Error is raised with original error.
	If onerror is passed, itll be called on exception.
	'''
	try:
		if stat.S_ISDIR(os.lstat(path).st_mode): rmdir(path)
		else: os.remove(path)
	except OSError as err:
		if onerror is None: raise Error(err)
		elif onerror is not False: onerror(path, err)


def rr(path, onerror=False, keep_root=False, **crawl_kwz):
	'''
	Recursively remove path.

	If exception(s) occur, an Error is raised with original error.
	If onerror is passed, itll be called on every raised exception.
	'''
	if onerror is False: onerror = lambda *args: None

	for entity in crawl(path, depth=True,
		onerror=onerror, **crawl_kwz): rm(entity, onerror=onerror)
	if not keep_root: rm(path, onerror)


def mv(src, dst, attrz=True, onerror=None):
	'''
	Recursively move a path.

	If the destination is on our current filesystem, then simply use
	rename.  Otherwise, copy src to the dst and then remove src.
	A lot more could be done here...  A look at a mv.c shows a lot of
	the issues this implementation glosses over.

	attrz determines whether privileged attrz like uid/gid will be
	manipulated. Timestamps are always preserved.
	'''
	try: os.rename(src, dst)
	except OSError:
		if _cmp(src, dst): raise Error('{0!r} and {1!r} are the same object.'.format(src,dst))
		err1 = cp_r( src, dst, dereference=False, attrz=attrz,
			onerror=onerror, atom=ft.partial(cp_d, skip_ts=False) )
		err2 = rr(src, onerror=onerror)
		if err1 is not None: return err1 + err2


from collections import deque

def walk(top, depth=False, relative=False, onerror=None, follow_links=False):
	'''Filesystem nodes iterator.
		Unlike os.walk it does not use recursion and never keeps any more
			nodes in memory than necessary (listdir returns generator, not lists).
		file/dir nodes' ordering in the same path is undefined.'''
	if not depth: # special case for root node
		rec_check = yield top
		if rec_check is False: raise StopIteration

	stack = deque([top])

	while stack:
		entries = stack[-1]
		if not isinstance(entries, types.StringTypes): path, entries = entries
		else:
			stack.pop()
			try: path, entries = entries, listdir(entries)
			except (OSError, IOError) as err:
				if depth: yield entries # no recursion here, so just yield
				if onerror is None: raise
				else:
					onerror(entries, err)
					continue
			else: stack.append((path, entries))

		for entry in it.imap(ft.partial(join, path), entries):
			try: chk = isdir(entry) and (follow_links or not islink(entry))
			except (OSError, IOError) as err:
				if onerror is None: raise
				else:
					onerror(entry, err)
					continue # only onerror should handle these
			if not chk: yield entry
			elif depth: # extend stack, recurse dir
				stack.append(entry)
				break
			elif (yield entry) is not False: stack.appendleft(entry)
		else: # done here, move up the stack
			if depth: yield path
			stack.pop()


def crawl(top, include=list(), exclude=list(),
		relative=False, recursive_patterns=False, **walk_kwz):
	'''Filesystem nodes iterator with filtering.
		With relative=True only the part of path after "top" is returned.
		"exclude" patterns are applied before "include",
			both are matched against "relative" part only.
		"recursive_patterns" flag enables include/exclude patterns to stop recursion.
			Ignored when depth=True.'''
	include, exclude = ( [re.compile(patterns)] if isinstance( patterns,
			types.StringTypes ) else list(re.compile(pat) for pat in patterns)
		for patterns in (include, exclude) )
	path_rel = lambda x, s=op.itemgetter(slice(len(top), None)): s(x).lstrip('/')

	iterator, chk = walk(top, **walk_kwz), True
	entry = next(iterator)
	while True:
		entry_rel = path_rel(entry)
		chk = not any(regex.search(entry_rel) for regex in exclude)\
			and (not include or any(regex.search(entry_rel) for regex in include))
		if chk: yield entry if not relative else entry_rel
		try: entry = iterator.send(not recursive_patterns or chk)
		except StopIteration: break


def touch(path, mode=0644, uid=-1, gid=-1):
	'Create or truncate a file with given stats.'
	open(path, 'w')
	os.chmod(path, mode)
	chown(path, *resolve_ids(uid, gid))


def mkdir(path, mode=0755, uid=-1, gid=-1, recursive=False):
	'Create a dir with given stats.'
	uid, gid = resolve_ids(uid, gid)
	ppath = path
	if recursive:
		stack = list()
		while ppath and not isdir(ppath):
			stack.insert(0, ppath)
			ppath = os.path.dirname(ppath)
	else: stack = [path]
	for ppath in stack:
		try:
			os.mkdir(ppath, mode)
			if uid != -1 or gid != -1: os.chown(ppath, uid, gid)
		except OSError as err: raise Error(err)


def ln(src, dst, hard=False, recursive=False):
	'Create a link'
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
_glob_cbex = re.compile(r'\{[^}]+\}')
def glob(pattern):
	'Globbing with curly-brace expansion'
	subs = list()
	while True:
		ex = _glob_cbex.search(pattern)
		if not ex: break
		subs.append(ex.group(0)[1:-1].split(','))
		pattern = pattern[:ex.span()[0]] + '{}' + pattern[ex.span()[1]:]
	return it.chain.from_iterable( iglob(pattern.format(*combo))\
		for combo in it.product(*subs) ) if subs else iglob(pattern)


def df(path):
	'Get (size, available) disk space, bytes'
	df = os.statvfs(path)
	return (df.f_blocks * df.f_bsize, df.f_bavail * df.f_bsize)


from io import open
from time import time
import signal, errno, fcntl

class LockError(Error): pass

def flock( filespec, contents=None,
		add_newline=True, block=False, fcntl_args=tuple() ):
	'''Simple and supposedly-reliable advisory file locking.
		Uses SIGALRM for timeout, if "block" argument is specified.
		filespec can be a path (bytes/unicode), fd (int) or file object.
		Returned file object can be safely discarded if it's built from fd or another object.'''

	try:
		lock = open(filespec, 'a+', closefd=isinstance(filespec, types.StringTypes))\
			if isinstance(filespec, (int, types.StringTypes)) else filespec
		if not block: fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB, *fcntl_args)
		else:
			prev_alarm = signal.alarm(block)
			if prev_alarm: prev_alarm = time() + prev_alarm
			prev_alarm_handler = signal.signal(signal.SIGALRM, lambda sig,frm: None)
			try: fcntl.lockf(lock, fcntl.LOCK_EX, *fcntl_args)
			except (OSError, IOError) as err:
				if err.errno != errno.EINTR: raise
				else: raise LockError('Timeout has passed ({})'.format(block))
			finally:
				signal.alarm(0) # so further calls won't get interrupted
				signal.signal(signal.SIGALRM, prev_alarm_handler)
				if prev_alarm:
					prev_alarm = prev_alarm - time()
					if prev_alarm > 0: signal.alarm(prev_alarm)
					else: os.kill(os.getpid(), signal.SIGALRM)

	except (IOError, OSError, LockError) as ex:
		raise LockError('Unable to acquire lockfile ({})): {}'.format(filespec, ex))

	if contents:
		lock.seek(0, os.SEEK_SET)
		lock.truncate()
		lock.write(b'{}{}'.format(contents, '\n' if add_newline else ''))
		lock.flush()

	return lock


from weakref import ref
_gc_beacon = set() # simple weakref'able collectable object
gc_refs = list()
def gc(*argz, **kwz):
	gc_refs.append(ref( _gc_beacon, argz[0] if not kwz
		and len(argz) == 1 and callable(argz[0]) else ft.partial(*argz, **kwz) ))

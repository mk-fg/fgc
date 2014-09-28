# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
'My extended version of standard py module "shutil"'


import itertools as it, operator as op, functools as ft

from contextlib import contextmanager
from . import os_ext, Error
import os, sys, stat, re, pwd, grp, types
import re, tempfile

try: from . import acl
except ImportError: acl = None

# These are also re-exported
from os.path import islink, isdir, isfile
from os import rmdir
from .os_ext import listdir



## Important rule for working with the paths:
## They ARE bytestrings and should NEVER be implicitly
##  converted to unicode, since there's no way to convert them
##  back, short of storing encoding along with the unicode object,
##  which pretty much what bytestring is.
## There can be a problem with this approach on xdev operations,
##  but "default fs encoding" detection seem to reliably fail, so fuck it.

def _force_bytestrings(paths):
	for path in paths:
		assert isinstance(path, types.StringTypes)
		yield bytes(path)

from os.path import join as _join
join = lambda *paths: _join(*_force_bytestrings(paths))





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


def relpath(path, from_path):
	path, from_path = it.imap(os.path.abspath, (path, from_path))
	from_path = os.path.dirname(from_path)
	path, from_path = it.imap(lambda x: x.split(os.sep), (path, from_path))
	for i in xrange(min(len(from_path), len(path))):
		if from_path[i] != path[i]: break
		else: i +=1
	return join(*([os.pardir] * (len(from_path)-i) + path[i:]))


def chown(path, uid=-1, gid=-1, recursive=False, dereference=True):
	'''Does not check for recursion-loops (although
		link-recursion will be avoided with dereference=False)'''
	uid, gid = resolve_ids(uid, gid)
	op = os.chown if dereference else os.lchown
	if not recursive: op(path, uid, gid)
	else:
		for path in walk(path, follow_links=dereference):
			if dereference and islink(path): os.lchown(path, uid, gid) # chown the link as well
			op(path, uid, gid)

def chmod(path, bits, dereference=True, merge=False):
	if merge:
		bits = stat.S_IMODE(( os.stat
			if dereference else os.lstat )(path).st_mode) | bits
	if dereference: os.chmod(path, bits)
	else:
		try: os.lchmod(path, bits)
		except AttributeError: # linux does not support symlink modes
			if not os.path.islink(path): os.chmod(path, bits)



from shutil import copyfileobj

def cat(fsrc, fdst, bs=16*1024, flush=False, sync=False):
	copyfileobj(fsrc, fdst, bs)
	if flush or sync: fdst.flush()
	if sync: os.fsync(fdst.fileno())


def samenode(src, dst):
	if not isdir(src):
		try: return os.path.samefile(src, dst)
		except OSError: return False
	else:
		return ( os.path.normcase(os.path.abspath(src))
			== os.path.normcase(os.path.abspath(dst)) )


def cp_data(src, dst, append=False, sync=False, trunc_call=False):
	'Copy data from src to dst'
	if samenode(src, dst):
		raise Error('{!r} and {!r} are the same file'.format(src, dst))
	if append: trunc_call = False
	with open(src, 'rb') as fsrc,\
			open(dst, ('wb' if not trunc_call else 'rb+') if not append else 'ab') as fdst:
		if trunc_call: fdst.truncate()
		cat(fsrc, fdst, sync=sync)


def cp_meta(src, dst, attrs=False, dereference=True, skip_ts=None):
	'Copy mode or full attrs (atime, mtime and ownership) from src to dst'
	chown, st, utime_set = (os.chown, os.stat, os.utime)\
		if dereference else (os.lchown, os.lstat, os_ext.lutimes)
	st = st(src) if isinstance(src, types.StringTypes) else src
	mode = stat.S_IMODE(st.st_mode)
	src_acl = None
	if attrs and acl and isinstance(src, (file, bytes, int)): # just not a stat result
		src_acl = set(acl.get(src, effective=False))
		if not acl.is_mode(src_acl):
			src_acl_eff = set(acl.get(src, effective=True))
			if src_acl != src_acl_eff: # apply full acl, chmod, then apply effective acl
				acl.apply(src_acl, dst)
				src_acl = src_acl_eff
		else:
			acl.unset(dst)
			src_acl = None
	if dereference: os.chmod(dst, mode)
	else:
		try: os.lchmod(dst, mode)
		except AttributeError: # linux does not support symlink modes
			if not os.path.islink(dst): os.chmod(dst, mode)
	if attrs:
		if src_acl: acl.apply(src_acl, dst)
		chown(dst, st.st_uid, st.st_gid)
	if (attrs if skip_ts is None else not skip_ts):
		if dereference and islink(dst): dst = os.readlink(dst)
		utime_set(dst, (st.st_atime, st.st_mtime))
	return st


def cp(src, dst, attrs=False, dereference=True, sync=False, skip_ts=None):
	'Copy data and mode bits ("cp src dst"). The destination may be a dir.'
	if isdir(dst): dst = join(dst, os.path.basename(src))
	if not any( f((os.stat if dereference else os.lstat)(src).st_mode) for f in
			op.attrgetter('S_ISREG', 'S_ISDIR', 'S_ISLNK')(stat) ):
		raise Error('Node is not a file/dir/link, cp of these is not supported.')
	cp_data(src, dst, sync=sync)
	return cp_meta(src, dst, attrs=attrs, skip_ts=skip_ts)

cp_p = lambda src,dst: cp(src, dst, attrs=True)

def cp_d(src, dst, attrs=False, dereference=True, sync=False, skip_ts=None):
	'Copy only one node, whatever it is.'
	if not dereference and islink(src):
		os.symlink(os.readlink(src), dst)
		return cp_meta( src, dst,
			dereference=False, attrs=attrs, skip_ts=skip_ts )
	elif isdir(src):
		try:
			os.mkdir(dst)
			return cp_meta(src, dst, attrs=attrs, skip_ts=skip_ts)
		except OSError as err: raise Error(err)
	else: return cp(src, dst, attrs=attrs, sync=sync, skip_ts=skip_ts)


def cp_r( src, dst, dereference=True,
		attrs=False, onerror=False, atom=cp_d, **crawl_kwz ):
	'''
	Recursively copy a directory tree.

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
	if onerror is False: errors, onerror = list(), lambda *args: errors.append(args)
	else: errors = None
	crawl_kwz.setdefault('follow_links', dereference)

	for entity in crawl( src, depth=False,
			relative=True, onerror=onerror, **crawl_kwz ):
		try:
			src_node, dst_node = (join(src, entity), join(dst, entity)) if entity else (src, dst)
			atom(src_node, dst_node, dereference=dereference, attrs=attrs)
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


def rr(path, onerror=False, **crawl_kwz):
	'''
	Recursively remove path.

	If exception(s) occur, an Error is raised with original error.
	If onerror is passed, itll be called on every raised exception.
	'''
	if onerror is False: onerror = lambda *args: None

	for entity in crawl(path, depth=True,
		onerror=onerror, **crawl_kwz): rm(entity, onerror=onerror)


def mv(src, dst, attrs=True, onerror=None):
	'''
	Recursively move a path.

	If the destination is on our current filesystem, then simply use
	rename.  Otherwise, copy src to the dst and then remove src.
	A lot more could be done here...  A look at a mv.c shows a lot of
	the issues this implementation glosses over.

	attrs determines whether privileged attrs like uid/gid will be
	manipulated. Timestamps are always preserved.
	'''
	try: os.rename(src, dst)
	except OSError:
		if samenode(src, dst): raise Error('{!r} and {!r} are the same node.'.format(src,dst))
		err1 = cp_r( src, dst, dereference=False, attrs=attrs,
			onerror=onerror, atom=ft.partial(cp_d, skip_ts=False) )
		err2 = rr(src, onerror=onerror)
		if err1 is not None: return err1 + err2


from collections import deque

def walk(top, depth=False, onerror=None, follow_links=False):
	'''Filesystem nodes iterator.
		Unlike os.walk it does not use recursion and never keeps any more
			nodes in memory than necessary (listdir returns generator, not lists).
		file/dir nodes' ordering in the same path is undefined.
		bool values can be passed back to iterator if depth=False to determine
			whether it should descend into returned path (if it is dir, naturally) or not.'''
	chk = isfile(top)
	if not depth or chk: # special case for root node
		if (yield top) is False or chk or (not follow_links and islink(top)): raise StopIteration

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

		for entry in (join(path, entry) for entry in entries):
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


def crawl(top, include=list(), exclude=list(), filter_func=None,
		relative=False, recursive_patterns=False, **walk_kwz):
	'''Filesystem nodes iterator with filtering.
		With relative=True only the part of path after "top" is returned.
		"exclude" patterns override "filter_func" which overrides "include",
			both are matched against "relative" part only.
		"recursive_patterns" flag enables include/exclude patterns to stop recursion.
			Ignored when depth=True.'''
	include, exclude = ( [re.compile(patterns)] if isinstance( patterns,
			types.StringTypes ) else list(re.compile(pat) for pat in patterns)
		for patterns in (include, exclude) )
	path_rel = lambda x, s=op.itemgetter(slice(len(top), None)): s(x).lstrip(b'/')

	iterator, chk = walk(top, **walk_kwz), True
	entry = next(iterator)
	while True:
		entry_rel = path_rel(entry)
		chk = not any(regex.search(entry_rel) for regex in exclude)\
			and (not filter_func or filter_func(entry, entry_rel))\
			and (not include or any(regex.search(entry_rel) for regex in include))
		if chk:
			chk = yield (entry if not relative else entry_rel)
			if chk is None: chk = True
		elif not recursive_patterns: chk = True # so "recursive_patterns" won't affect .send()
		try: entry = iterator.send(chk)
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
		subs.append(ex.group(0)[1:-1].split(b','))
		pattern = pattern[:ex.span()[0]] + b'{}' + pattern[ex.span()[1]:]
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

def flock( filespec, contents=None, shared=False,
		add_newline=True, block=False, fcntl_args=tuple() ):
	'''Simple and supposedly-reliable advisory file locking.
		Uses SIGALRM for timeout, if "block" argument is specified.
		filespec can be a path (bytes/unicode), fd (int) or file object.
		Returned file object can be safely discarded if it's built from fd or another object.'''

	shared = fcntl.LOCK_EX if not shared else fcntl.LOCK_SH
	try:
		lock = open(filespec, 'ab+', closefd=isinstance(filespec, types.StringTypes))\
			if isinstance(filespec, (int, types.StringTypes)) else filespec
		if not block: fcntl.lockf(lock, shared | fcntl.LOCK_NB, *fcntl_args)
		else:
			prev_alarm = signal.alarm(block)
			if prev_alarm: prev_alarm = time() + prev_alarm
			prev_alarm_handler = signal.signal(signal.SIGALRM, lambda sig,frm: None)
			try: fcntl.lockf(lock, shared, *fcntl_args)
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
		lock.write('{}{}'.format(contents, '\n' if add_newline else ''))
		lock.flush()

	return lock


_xmatch_pat_cache = {}

def _fn_xmatch_pat(pat):
	# From sphinx.util.matching
	i, n, res = 0, len(pat), ''
	while i < n:
		c, i = pat[i], i + 1
		if c == '*':
			# double star matches slashes too
			if i < n and pat[i] == '*': res, i = res + '.*', i + 1
			# single star doesn't match slashes
			else: res = res + '[^/]*'
		# question mark doesn't match slashes too
		elif c == '?': res = res + '[^/]'
		elif c == '[':
			j = i
			if j < n and pat[j] == '!': j += 1
			if j < n and pat[j] == ']': j += 1
			while j < n and pat[j] != ']': j += 1
			if j >= n: res = res + '\\['
			else:
				stuff, i = pat[i:j].replace('\\', '\\\\'), j + 1
				# negative pattern mustn't match slashes too
				if stuff[0] == '!': stuff = '^/' + stuff[1:]
				elif stuff[0] == '^': stuff = '\\' + stuff
				res = '{}[{}]'.format(res, stuff)
		else: res += re.escape(c)
	return re.compile('^' + res + '$')

def fn_xmatch_pat(pat):
	if pat not in _xmatch_pat_cache:
		_xmatch_pat_cache[pat] = _fn_xmatch_pat(pat)
	return _xmatch_pat_cache[pat]

def fn_xmatch(pat, name):
	'Same as fnmatch, but proper arg order and only matches slashes by **.'
	return fn_xmatch_pat(pat).search(name)


@contextmanager
def dump_tempfile(path):
	kws = dict( delete=False,
		dir=os.path.dirname(path), prefix=os.path.basename(path)+'.' )
	with NamedTemporaryFile(**kws) as tmp:
		try:
			yield tmp
			tmp.flush()
			os.rename(tmp.name, path)
		finally:
			try: os.unlink(tmp.name)
			except (OSError, IOError): pass


from weakref import ref
_gc_beacon = set() # simple weakref'able collectable object
gc_refs = list()
def gc(*argz, **kwz):
	gc_refs.append(ref( _gc_beacon, argz[0] if not kwz
		and len(argz) == 1 and callable(argz[0]) else ft.partial(*argz, **kwz) ))

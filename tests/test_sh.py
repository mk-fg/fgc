# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function
import itertools as it, operator as op, functools as ft


import unittest
from nose import with_setup

import os, sys, re, string, types, stat
from fgc import sh, dta
from random import shuffle, choice
from hashlib import md5
from tempfile import mkdtemp, mkstemp
from io import open
from time import time

from fgc.od import do


class tp(dict): # TestPath
	__slots__ = 'name', 'path', 'suite', 'contents'

	def __init__(self, *subpaths, **kwz):
		for k,v in kwz.viewitems(): setattr(self, k, v)
		self.contents = subpaths

	def __str__(self): return str(self.__unicode__())
	def __unicode__(self): return self.path

	def create(self):
		if not self.path: raise KeyError
		for node in self.contents:
			name = self.suite.file_name
			if isinstance(node, tp):
				node.suite, node.path = self.suite, mkdtemp(prefix=name, dir=self.path)
				node.create()
				node, path = node.name, node
			else:
				fd, path = mkstemp(prefix=name, dir=self.path)
				open(fd, 'wb').write(self.suite.file_content + bytes(self.suite.uid))
			self[node] = path
		del self.contents
		return self

	def node(self, nid, tp=None):
		path = self[nid] = os.path.join(self.path, self.suite.file_name)
		if tp is not None:
			tp.path, tp.suite = path, self.suite
			tp.create()
		return path




get_mode = lambda path: stat.S_IMODE(os.lstat(path).st_mode)
get_utime = lambda path, dr=True: op.attrgetter('st_atime', 'st_mtime')((os.stat if dr else os.lstat)(path))


def _skipUnlessUids(check_root=True, check_reverse=False):
	if check_root and os.geteuid() != 0:
		return unittest.skip('Superuser access required')

	import pwd, grp
	uname, gname = 'nobody', 'nogroup'
	try: uid, gid = pwd.getpwnam(uname).pw_uid, grp.getgrnam(gname).gr_gid
	except KeyError:
		return unittest.skip('IDs of nobody/nogroup cannot be determined')

	if not check_reverse: return lambda func: ft.wraps(func)(lambda s: func(s, uname, gname, uid, gid))
	else:
		try:
			if pwd.getpwuid(uid).pw_name != uname\
				or grp.getgrgid(gid).gr_name != gname: raise KeyError
		except KeyError:
			return unittest.skip('Reverse resolution of IDs for nobody/nogroup failed')
		nxuid = nxgid = None
		for nxid in xrange(max(uid, gid), 0, -1):
			try: pwd.getpwuid(nxid)
			except KeyError: nxuid = nxid
			try: grp.getgrgid(nxid)
			except KeyError: nxgid = nxid
			if nxuid and nxgid: break
		else: return unittest.skip('Unable to find free uid/gid')
		return lambda func: ft.wraps(func)(lambda s: func(s, uname, gname, uid, gid, nxuid, nxgid))


class SH_TestFilesBase(unittest.TestCase):

	file_content_unicode = 'Съешь ещё этих аццких'\
		' олбанских креведок, да выпей йаду, сцуко!'
	file_content_hr = 'Jackdaws love'\
		' my big sphinx of quartz. {}'.format(file_content_unicode)

	_uid = it.chain.from_iterable(it.imap(xrange, it.repeat(2**30))).next
	uid = dta.static_property(_uid)

	# Note: I don't give a fuck about filenames with non-ascii chars
	file_name = dta.static_property(it.imap(
		lambda s: shuffle(s) or unicode(s),
		it.repeat(bytearray(dta.uid(20) + b' '*3 + b'."_-!\'')) ).next)

	file_content = dta.static_property(it.imap(
		lambda s: shuffle(s) or unicode(s),
		it.repeat(bytearray(string.printable*5 + string.whitespace*3)) ).next)

	tmp_dir = property( lambda self,fngen=file_name.fget:\
		mkdtemp(prefix='fgc.test.{}'.format(fngen(self))) )

	tmp_dir_idx = tmp_dir_gc = None

	def setUp(self):
		tmp_dir = self.tmp_dir_gc = self.tmp_dir
		idx = self.tmp_dir_idx = tp(
				'file', 'file_l0',
				tp(name='empty'),
				tp(*(['file']*3 + ['file_l1']), name='files'),
				tp(*(['file']*3 + [
					tp(*(['file']*3 + ['file_l2']), name='h11'),
					tp(*(['file']*3 + ['file_lh']), name='h12') ]), name='h1'),
			name='root', path=tmp_dir, suite=self ).create()
		# File symlinks
		os.symlink(unicode(idx['file_l0']), idx['h1']['h12'].node('link_l0'))
		os.symlink(unicode(idx['files']['file_l1']), idx['h1'].node('link_l1'))
		os.symlink(unicode(idx['h1']['h11']['file_l2']), idx.node('link_l2'))
		# Dir symlinks
		os.symlink(unicode(idx['h1']), idx.node('link_d0'))
		os.symlink(unicode(idx['files']), idx['h1']['h11'].node('link_d1'))
		os.symlink(unicode(idx), idx['h1']['h12'].node('link_d2'))
		# Hardlink
		os.link(unicode(idx['h1']['h12']['file_lh']), idx['h1']['h11'].node('link_lh'))

	def tearDown(self):
		for root, dirs, files in os.walk( self.tmp_dir_gc,
				topdown=False, followlinks=False, onerror=lambda x: None ):
			for name in files+dirs:
				name = os.path.join(root, name)
				if os.path.isfile(name) or os.path.islink(name): os.remove(name)
				else: os.rmdir(name)
		os.rmdir(self.tmp_dir_gc)

	def assertAllEqual(self, chk, *argz):
		for arg in argz: self.assertEqual(chk, arg)
	def assertContents(self, chk, *argz):
		for arg in argz: self.assertEqual(chk, open(arg, 'rb').read())
	def assertModes(self, chk, *argz):
		for arg in argz: self.assertEqual(chk, os.lstat(arg).st_mode)

	def assertIDs(self, path, uid, gid):
		self.assertEqual(os.lstat(path).st_uid, uid)
		self.assertEqual(os.lstat(path).st_gid, gid)



class SH_TestFilesMacro(SH_TestFilesBase):

	def setUp(self, stats=True):
		super(SH_TestFilesMacro, self).setUp()

		self.links = self.tmp_dir_idx['h1']['h12']['link_l0'], self.tmp_dir_idx['h1']['link_l1']
		self.files = self.tmp_dir_idx['file_l0'], self.tmp_dir_idx['files']['file_l1']
		self.hl = self.tmp_dir_idx['h1']['h12']['file_lh'], self.tmp_dir_idx['h1']['h11']['link_lh']
		self.dir = unicode(self.tmp_dir_idx['h1'])
		self.dir_link = self.tmp_dir_idx['link_d0']

		os.chmod(self.files[0], 0751)
		os.chmod(self.files[1], 0640)
		os.chmod(self.dir, 0750)

		if stats: self.setUpStats()

	def setUpStats(self):
		self.lstats = tuple(os.lstat(path).st_mode for path in self.links)
		self.ltargets = tuple(os.readlink(path) for path in self.links)
		self.fstats = tuple(os.stat(path).st_mode for path in self.files)
		self.contents = tuple(open(path, 'rb').read() for path in self.files)
		self.dstat = os.lstat(self.dir).st_mode
		self.dlstat = os.lstat(self.dir_link).st_mode


	def assertLinkModes(self):
		for pair in it.izip(self.lstats, self.links): self.assertModes(*pair)
	def assertLinkTargets(self):
		for path,link in it.izip(self.ltargets, self.links): self.assertEqual(path, os.readlink(link))

	def assertFileModes(self):
		for pair in it.izip(self.fstats, self.files): self.assertModes(*pair)
	def assertFileContents(self):
		for pair in it.izip(self.contents, self.files): self.assertModes(*pair)

	def assertFileModesEqual(self):
		self.assertModes(self.fstats[0], *self.files)
	def assertFileContentsEqual(self):
		self.assertContents(self.contents[0], *self.files)

	def assertTimesEqual(self, *paths, **kwz):
		func, delta = kwz.get('func', self.assertAlmostEqual), kwz.get('delta', 1)
		# Times will differ in some nth decimal places, hence "almost"
		atime_chk, mtime_chk = get_utime(paths[0])
		for atime, mtime in it.imap(get_utime, paths[1:]):
			if kwz.get('atime_check', True): func(atime, atime_chk, delta=delta)
			func(mtime, mtime_chk, delta=delta)
	def assertTimesNotEqual(self, *paths, **kwz):
		if 'func' not in kwz: kwz['func'] = self.assertNotAlmostEqual
		self.assertTimesEqual(*paths, **kwz)



class SH_TestCat(SH_TestFilesMacro):

	def test_cat_simple(self):
		sh.cat(open(self.files[0], 'rb'), open(self.files[1], 'wb'))
		self.assertFileContentsEqual()

	def test_cat_links(self):
		sh.cat(open(self.files[0], 'rb'), open(self.files[1], 'wb'))
		self.assertFileModes()
		self.assertFileContentsEqual()

	def test_cat_samefile(self):
		sh.cat(open(self.hl[0], 'rb'), open(self.hl[1], 'wb'))
		self.assertEqual(open(self.hl[0], 'rb').read(), '')
		self.assertTrue(os.path.samefile(*self.hl))

	def test_cat_sync(self):
		(src, dst), src_content = self.files, self.contents[0]

		with open(dst, 'wb', 8*1024) as dst_file:
			sh.cat(open(src, 'rb'), dst_file)
			self.assertNotEqual(open(dst, 'rb').read(), src_content)
			dst_file.flush()
			self.assertFileContentsEqual()

		with open(dst, 'wb', 8*1024) as dst_file:
			sh.cat(open(src, 'rb'), dst_file, flush=True)
			self.assertFileContentsEqual()

		# No check whether actual data hit the disk, but it should at least result in flush
		with open(dst, 'wb', 8*1024) as dst_file:
			sh.cat(open(src, 'rb'), dst_file, sync=True)
			self.assertFileContentsEqual()



class SH_TestIDs(SH_TestFilesBase):

	@_skipUnlessUids(check_root=False)
	def test_ids(self, uname, gname, uid, gid):
		self.assertEqual(sh.to_uid(uid), uid)
		self.assertEqual(sh.to_uid(uname), uid)
		self.assertEqual(sh.to_gid(gid), gid)
		self.assertEqual(sh.to_gid(gname), gid)

		self.assertEqual(tuple(sh.resolve_ids(uid, gid)), (uid, gid))
		self.assertEqual(tuple(sh.resolve_ids(uname, gid)), (uid, gid))
		self.assertEqual(tuple(sh.resolve_ids(uid, gname)), (uid, gid))
		self.assertEqual(tuple(sh.resolve_ids(None, None)), (-1, -1))
		self.assertEqual(tuple(sh.resolve_ids(-1, -1)), (-1, -1))
		self.assertEqual(tuple(sh.resolve_ids('{}:{}'.format(uname, gname))), (uid, gid))

	@_skipUnlessUids(check_root=False, check_reverse=True)
	def test_ids_reverse(self, uname, gname, uid, gid, nxuid, nxgid):
		self.assertEqual(sh.to_uname(uid), uname)
		self.assertEqual(sh.to_uname(nxuid), nxuid)
		self.assertEqual(sh.to_gname(gid), gname)
		self.assertEqual(sh.to_uname(nxgid), nxgid)



class SH_TestChmod(SH_TestFilesMacro):

	def test_chmod_basic(self):
		sh.chmod(self.files[0], 0644)
		self.assertEqual(get_mode(self.files[0]), 0644)
		self.assertNotEqual(os.stat(self.files[0]).st_mode, self.fstats[0])
		sh.chmod(self.dir, 0755)
		self.assertEqual(get_mode(self.dir), 0755)
		self.assertNotEqual(os.stat(self.dir).st_mode, self.dstat)

	def test_chmod_link1(self):
		file_, link = self.files[0], self.links[0]

		sh.chmod(link, 0644)
		self.assertNotEqual(os.stat(file_).st_mode, self.fstats[0])
		self.assertEqual(get_mode(file_), 0644)
		self.assertLinkModes()

		sh.chmod(link, 0600, dereference=True)
		self.assertEqual(get_mode(file_), 0600)
		self.assertLinkModes()

	def test_chmod_link2(self):
		file_, link = self.files[0], self.links[0]
		if hasattr(os, 'lchmod'):
			os.lchmod(link, 0750)
			self.assertNotEqual(os.lstat(link).st_mode, self.lstats[0])
			self.assertEqual(get_mode(link), 0750)
			self.assertFileModes()
			sh.chmod(link, 0755, dereference=False)
			self.assertEqual(get_mode(link), 0755)
			self.assertFileModes()
		else: # link chmod should not affect the file, at least
			sh.chmod(link, 0755, dereference=False)
			self.assertFileModes()

	def test_chmod_merge1(self):
		sh.chmod(self.files[1], 0134, merge=True)
		self.assertEqual(get_mode(self.files[1]), 0774)

	def test_chmod_merge2(self):
		sh.chmod(self.files[1], 0660, merge=True)
		self.assertEqual(get_mode(self.files[1]), 0660)

	def test_chmod_merge_link(self):
		file_, link = self.files[1], self.links[1]
		if hasattr(os, 'lchmod'):
			os.lchmod(link, 0750)
			sh.chmod(link, 0625, dereference=False, merge=True)
			self.assertEqual(get_mode(link), 0775)
			self.assertEqual(get_mode(file_), 0640)
			sh.chmod(link, 0777, dereference=True, merge=True)
			self.assertEqual(get_mode(link), 0775)
			self.assertEqual(get_mode(file_), 0777)

		else: # link chmod should not affect the file, at least
			link_mode = stat.S_IMODE(self.lstats[1])

			sh.chmod(link, 0775, dereference=False, merge=True)
			self.assertEqual(get_mode(link), link_mode)
			self.assertEqual(get_mode(file_), 0640)

			sh.chmod(link, 0777, dereference=True, merge=True)
			self.assertEqual(get_mode(link), link_mode)
			self.assertEqual(get_mode(file_), 0777)

	@unittest.skipUnless(os.geteuid() == 0, 'Superuser access required')
	def test_chmod_super(self):
		file_, dir_ = self.files[0], self.dir
		sh.chmod(file_, 04700)
		self.assertEqual(get_mode(file_), 04700)
		sh.chmod(dir_, 02700, merge=True)
		self.assertEqual(get_mode(dir_), 02750)
		sh.chmod(dir_, 03000, merge=True)
		self.assertEqual(get_mode(dir_), 03750)



class SH_TestChown(SH_TestFilesMacro):

	@_skipUnlessUids()
	def test_chown_simple(self, uname, gname, uid, gid):
		file_, chk = self.files[0], self.assertIDs
		os.lchown(file_, 0, 0)

		sh.chown(file_, uid, gid), chk(file_, uid, gid)
		sh.chown(file_, uid=0, gid=0), chk(file_, 0, 0)
		sh.chown(file_, uid=uid), chk(file_, uid, 0)
		sh.chown(file_, 0), chk(file_, 0, 0)
		sh.chown(file_, gid=gid), chk(file_, 0, gid)
		sh.chown(file_, uid, -1), chk(file_, uid, gid)
		sh.chown(file_, -1, 0), chk(file_, uid, 0)
		sh.chown(file_, -1, -1), chk(file_, uid, 0)
		sh.chown(file_, None, None), chk(file_, uid, 0)
		sh.chown(file_, None, gid), chk(file_, uid, gid)
		sh.chown(file_, 0, None), chk(file_, 0, gid)
		sh.chown(file_, 0, 0), chk(file_, 0, 0)
		sh.chown(file_, uname, gname), chk(file_, uid, gid)

		os.lchown(self.links[0], uid, gid)
		sh.chown(self.links[0], 0, 0, dereference=False)
		chk(file_, uid, gid), chk(self.links[0], 0, 0)

	@_skipUnlessUids()
	def test_chown_recursive(self, uname, gname, uid, gid):
		dir_, dir_link, chk = self.dir, self.dir_link, self.assertIDs
		file_, link, link_file = self.tmp_dir_idx['h1']['file'],\
			self.tmp_dir_idx['h1']['h12']['link_l0'], self.tmp_dir_idx['file_l0']
		os.lchown(dir_link, uid, gid), os.lchown(link, uid, gid)
		os.chown(dir_, uid, gid), os.chown(file_, uid, gid), os.chown(link_file, uid, gid)

		sh.chown(dir_link, 0, 0, dereference=False)
		chk(dir_, uid, gid), chk(file_, uid, gid), chk(dir_link, 0, 0)

		sh.chown(dir_link, 0, gid, dereference=False, recursive=True)
		chk(dir_link, 0, gid)
		chk(dir_, uid, gid), chk(file_, uid, gid), chk(link, uid, gid), chk(link_file, uid, gid)
		sh.chown(dir_, 0, gid, dereference=False, recursive=True)

		# Recursive link should produce endless loop on dereference
		os.remove(self.tmp_dir_idx['h1']['h12']['link_d2'])

		sh.chown(dir_link, 0, 0, recursive=True)
		chk(dir_, 0, 0), chk(file_, 0, 0)
		chk(dir_link, 0, 0), chk(link, 0, 0), chk(link_file, 0, 0)
		sh.chown(dir_link, uid, 0, dereference=True, recursive=True)
		chk(dir_, uid, 0), chk(file_, uid, 0)
		chk(dir_link, uid, 0), chk(link, uid, 0), chk(link_file, uid, 0)



class SH_TestCpData(SH_TestFilesMacro):

	def test_cp_data(self):
		sh.cp_data(*self.files)
		self.assertFileModes()
		self.assertFileContentsEqual()

	def test_cp_data_links1(self):
		sh.cp_data(*self.links)
		self.assertLinkModes()
		self.assertLinkTargets()
		self.assertFileContentsEqual()

	def test_cp_data_links2(self):
		sh.cp_data(self.links[0], self.files[1])
		self.assertLinkModes()
		self.assertLinkTargets()
		self.assertFileModes()
		self.assertFileContentsEqual()

	def test_cp_data_append(self):
		sh.cp_data(*self.files, append=True)
		self.assertEqual(self.contents[1] + self.contents[0], open(self.files[1], 'rb').read())



# class SH_TestCpMeta(SH_TestFilesMacro):

# 	def setUp(self, stats=True):
# 		super(SH_TestCpMeta, self).setUp(stats=False)
# 		self.dirs = unicode(self.tmp_dir_idx['h1'])
# 		self.dir_links = self.tmp_dir_idx['link_d0']

# 	def test_cp_meta_basic(self):
# 		mode, utime = 0751, (time() - 300, time() - 500)

# 		file1, file2 = self.tmp_dir_idx['file_l0'], self.tmp_dir_idx['files']['file_l1']
# 		link1, link2 = self.tmp_dir_idx['h1']['h12']['link_l0'], self.tmp_dir_idx['h1']['link_l1']
# 		dir1, dir2 = it.imap(unicode, op.itemgetter('empty', 'files')(self.tmp_dir_idx))
# 		os.chmod(file1, mode), os.chmod(file2, 0600)
# 		os.utime(file1, utime), os.utime(file2, (time(), time()))

# 		cmp_utimes = self._cmp_utimes

# 		if hasattr(os, 'lchmod'):
# 			os.lchmod(link1, 777), os.lchmod(link2, 777)
# 		self.assertEqual(get_mode(link1, dr=False), get_mode(link2, dr=False))

# 		# There's just no standard substitute for this
# 		try: from os_ext import lutimes
# 		except ImportError: lutimes = False
# 		else:
# 			lutime1, lutime2 = (time() - 500, time() - 900), (time() - 600, time() - 1000)
# 			lutimes(link1, lutime1), lutimes(link2, lutime2)
# 			cmp_utimes(link1, link2, ne=True, dr=False)

# 		sh.cp_meta(file1, file2)
# 		self.assertEqual(mode, get_mode(file1))
# 		self.assertEqual(mode, get_mode(file2))
# 		cmp_utimes(file1, file2, ne=True)

# 		os.chmod(file2, 0600)
# 		sh.cp_meta(file1, file2, skip_ts=True)
# 		self.assertEqual(mode, get_mode(file2))
# 		cmp_utimes(file1, file2, ne=True)

# 		os.chmod(file2, 0600)
# 		sh.cp_meta(file1, file2, skip_ts=False)
# 		self.assertEqual(mode, get_mode(file2))
# 		cmp_utimes(file1, file2)

# 		sh.cp_meta(file1, dir1, skip_ts=False)
# 		self.assertEqual(mode, get_mode(dir1))
# 		cmp_utimes(file1, dir1)

# 		sh.cp_meta(dir1, dir2, skip_ts=False)
# 		self.assertEqual(mode, get_mode(dir1))
# 		self.assertEqual(mode, get_mode(dir2))
# 		cmp_utimes(dir1, dir2)

# 		os.chmod(file2, 0600), os.utime(file2, (0, 0))
# 		sh.cp_meta(file1, link2, skip_ts=False)
# 		if lutimes: cmp_utimes(file1, link2, ne=True, dr=False)
# 		self.assertNotEqual(mode, get_mode(link2, dr=False))
# 		self.assertEqual(mode, get_mode(file2))
# 		self.assertEqual(get_mode(link1), get_mode(link2))
# 		cmp_utimes(file1, file2)

# 		if lutimes: lutimes(link1, lutime1), lutimes(link2, lutime2)
# 		os.chmod(file2, 0600), os.utime(file2, (0, 0))
# 		sh.cp_meta(link1, link2, dereference=True, skip_ts=False)
# 		if lutimes: cmp_utimes(file1, link2, ne=True, dr=False, mtime_only=True)
# 		self.assertNotEqual(mode, get_mode(link2, dr=False))
# 		self.assertEqual(mode, get_mode(file2))
# 		self.assertEqual(get_mode(link1), get_mode(link2))
# 		cmp_utimes(file1, file2)

# 		os.chmod(file2, 0600), os.utime(file2, (0, 0))
# 		sh.cp_meta(link1, link2, dereference=False, skip_ts=False)
# 		if lutimes: cmp_utimes(link1, link2, dr=False)
# 		self.assertNotEqual(get_mode(file1), get_mode(link2, dr=False))
# 		self.assertNotEqual(get_mode(file1), get_mode(file2))
# 		cmp_utimes(file1, file2, ne=True)
# 		self.assertEqual(get_mode(link1, dr=False), get_mode(link2, dr=False))

# 		if hasattr(os, 'lchmod'):
# 			os.lchmod(link2, 700)
# 			sh.cp_meta(link1, link2, dereference=False, skip_ts=False)
# 			self.assertEqual(get_mode(link1, dr=False), get_mode(link2, dr=False))
# 		else:
# 			link2_mode = get_mode(link2, dr=False)
# 			sh.cp_meta(file1, link2, dereference=False, skip_ts=False)
# 			self.assertEqual(link2_mode, get_mode(link2, dr=False))

# 		if lutimes:
# 			lutimes(link1, lutime1), lutimes(link2, lutime2)
# 			sh.cp_meta(link1, link2, dereference=False)
# 			cmp_utimes(link1, link2, ne=True, dr=False)

# 	@_skipUnlessUids()
# 	def test_cp_meta_attrz(self, uname, gname, uid, gid):
# 		file1, file2 = self.tmp_dir_idx['file_l0'], self.tmp_dir_idx['files']['file_l1']

# 		os.chown(file1, uid, gid), os.chown(file2, 0, 0)
# 		os.chmod(file1, 0751), os.chmod(file2, 0600)
# 		os.utime(file1, (time() - 300, time() - 500)), os.utime(file2, (time(), time()))

# 		cmp_utimes = self._cmp_utimes

# 		sh.cp_meta(file1, file2, attrz=True)
# 		self.assertEqual(get_mode(file1), get_mode(file2))
# 		cmp_utimes(file1, file2)
# 		self.assertTrue( os.stat(file1).st_uid\
# 			== os.stat(file2).st_uid and os.stat(file1).st_uid == uid )
# 		self.assertTrue( os.stat(file1).st_gid\
# 			== os.stat(file2).st_gid and os.stat(file1).st_gid == gid )

# 		link1, link2 = self.tmp_dir_idx['h1']['h12']['link_l0'], self.tmp_dir_idx['h1']['link_l1']
# 		os.lchown(link1, uid, 0), os.lchown(link2, 0, gid)
# 		if hasattr(os, 'lchmod'): os.lchmod(link1, 0751), os.lchmod(link2, 0700)

# 		# There's just no standard substitute for this
# 		try: from os_ext import lutimes
# 		except ImportError: lutimes = False
# 		else:

# 		sh.cp_meta(link1, link2, dereference=False)
# 		self.assertEqual(get_mode(link1, dr=False), get_mode(link2, dr=False))
# 		cmp_utimes(file1, file2)
# 		self.assertTrue( os.stat(file1).st_uid\
# 			== os.stat(file2).st_uid and os.stat(file1).st_uid == uid )
# 		self.assertTrue( os.stat(file1).st_gid\
# 			== os.stat(file2).st_gid and os.stat(file1).st_gid == gid )











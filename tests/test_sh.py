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
get_utime = lambda path: op.attrgetter('st_atime', 'st_mtime')(os.lstat(path))


def getnxname():
		import pwd, grp
		while True:
			nxname = 'nxuser{}'.format(SH_TestFilesBase._uid())
			try: pwd.getpwnam(nxname)
			except KeyError: pass
			else: continue
			try: grp.getgrnam(nxname)
			except KeyError: pass
			else: continue
			return nxname

def skipUnlessUids(check_root=True, check_reverse=False):
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
		if os.getuid() == 0: os.seteuid(0), os.setegid(0)
		for root, dirs, files in os.walk( self.tmp_dir_gc,
				topdown=False, followlinks=False, onerror=lambda x: None ):
			for name in files+dirs:
				name = os.path.join(root, name)
				if os.path.isdir(name) and not os.path.islink(name): os.rmdir(name)
				else: os.remove(name)
		os.rmdir(self.tmp_dir_gc)

	def assertAllEqual(self, chk, *argz):
		for arg in argz: self.assertEqual(chk, arg)
	def assertContents(self, chk, *argz):
		for arg in argz: self.assertEqual(chk, open(arg, 'rb').read())
	def assertModes(self, chk, *argz, **kwz):
		stat_func = kwz.get('stat_func', lambda path: os.lstat(path).st_mode)
		func = kwz.get('func', self.assertEqual)
		for arg in argz: func(chk, stat_func(arg))

	def assertIDs(self, uid, gid, *paths):
		for path in paths:
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
		self.nxfile = self.tmp_dir_idx.node('nxfile')

		os.chmod(self.files[0], 0751)
		os.chmod(self.files[1], 0640)
		os.chmod(self.dir, 0750)

		if stats: self.setUpStats()

	def setUpStats(self):
		self.lstats = tuple(os.lstat(path).st_mode for path in self.links)
		self.fstats = tuple(os.stat(path).st_mode for path in self.files)
		self.contents = tuple(open(path, 'rb').read() for path in self.files)
		self.dstat = os.lstat(self.dir).st_mode
		self.dlstat = os.lstat(self.dir_link).st_mode


	def assertLinkModes(self):
		for pair in it.izip(self.lstats, self.links): self.assertModes(*pair)
	def assertLinkTargets(self):
		for path,link in it.izip(self.files, self.links): self.assertEqual(path, os.readlink(link))

	def assertFileModes(self):
		for pair in it.izip(self.fstats, self.files): self.assertModes(*pair)
	def assertFileContents(self):
		for pair in it.izip(self.contents, self.files): self.assertContents(*pair)

	def assertModesEqual(self, *files, **kwz):
		if 'stat_func' not in kwz: kwz['stat_func'] = lambda path: os.lstat(path).st_mode
		if 'mode' not in kwz: mode, files = kwz['stat_func'](files[0]), files[1:]
		else: mode = kwz.pop('mode')
		if not files: files = self.files
		self.assertModes(mode, *files, **kwz)
	def assertModesNotEqual(self, *files, **kwz):
		if 'func' not in kwz: kwz['func'] = self.assertNotEqual
		self.assertModesEqual(*files, **kwz)
	def assertFileModesEqual(self, *files, **kwz):
		if 'mode' not in kwz: kwz['mode'] = self.fstats[0]
		self.assertModesEqual(*files, **kwz)
	def assertContentsEqual(self, *files, **kwz):
		contents = kwz.get('contents', self.contents[0])
		if contents is False: contents, files = open(files[0], 'rb').read(), files[1:]
		if not files: files = self.files
		self.assertContents(contents, *files)

	def assertTimesEqual(self, *paths, **kwz):
		func, delta = kwz.get('func', self.assertAlmostEqual), kwz.get('delta', 1)
		# Times will differ in some nth decimal places, hence "almost"
		if 'times' in kwz: atime_chk, mtime_chk = kwz['times']
		else: (atime_chk, mtime_chk), paths = get_utime(paths[0]), paths[1:]
		for atime, mtime in it.imap(get_utime, paths):
			if kwz.get('atime_check', True): func(atime, atime_chk, delta=delta)
			func(mtime, mtime_chk, delta=delta)
	def assertTimesNotEqual(self, *paths, **kwz):
		if 'func' not in kwz: kwz['func'] = self.assertNotAlmostEqual
		self.assertTimesEqual(*paths, **kwz)



class SH_TestCat(SH_TestFilesMacro):

	def test_exc(self):
		with self.assertRaises(Exception): sh.cat(*self.files)

	def test_simple(self):
		sh.cat(open(self.files[0], 'rb'), open(self.files[1], 'wb'))
		self.assertContentsEqual()

	def test_links(self):
		sh.cat(open(self.files[0], 'rb'), open(self.files[1], 'wb'))
		self.assertFileModes()
		self.assertContentsEqual()

	def test_samefile(self):
		sh.cat(open(self.hl[0], 'rb'), open(self.hl[1], 'wb'))
		self.assertEqual(open(self.hl[0], 'rb').read(), '')
		self.assertTrue(os.path.samefile(*self.hl))

	def test_sync(self):
		(src, dst), src_content = self.files, self.contents[0]

		with open(dst, 'wb', 8*1024) as dst_file:
			sh.cat(open(src, 'rb'), dst_file)
			self.assertNotEqual(open(dst, 'rb').read(), src_content)
			dst_file.flush()
			self.assertContentsEqual()

		with open(dst, 'wb', 8*1024) as dst_file:
			sh.cat(open(src, 'rb'), dst_file, flush=True)
			self.assertContentsEqual()

		# No check whether actual data hit the disk, but it should at least result in flush
		with open(dst, 'wb', 8*1024) as dst_file:
			sh.cat(open(src, 'rb'), dst_file, sync=True)
			self.assertContentsEqual()



class SH_TestIDs(SH_TestFilesBase):

	def test_exc(self):
		nxname = getnxname()
		with self.assertRaises(KeyError): sh.to_uid(nxname)
		with self.assertRaises(KeyError): sh.to_gid(nxname)

	@skipUnlessUids(check_root=False)
	def test_straight(self, uname, gname, uid, gid):
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

	@skipUnlessUids(check_root=False, check_reverse=True)
	def test_reverse(self, uname, gname, uid, gid, nxuid, nxgid):
		self.assertEqual(sh.to_uname(uid), uname)
		self.assertEqual(sh.to_uname(nxuid), nxuid)
		self.assertEqual(sh.to_gname(gid), gname)
		self.assertEqual(sh.to_uname(nxgid), nxgid)



class SH_TestChmod(SH_TestFilesMacro):

	def test_exc(self):
		with self.assertRaises(OSError): sh.chmod(self.nxfile, 0750)

	@skipUnlessUids()
	def test_exc_super(self, uname, gname, uid, gid):
		os.setegid(gid), os.seteuid(uid)
		with self.assertRaises(OSError): sh.chmod(self.files[0], 04700)

	def test_basic(self):
		sh.chmod(self.files[0], 0644)
		self.assertEqual(get_mode(self.files[0]), 0644)
		self.assertNotEqual(os.stat(self.files[0]).st_mode, self.fstats[0])
		sh.chmod(self.dir, 0755)
		self.assertEqual(get_mode(self.dir), 0755)
		self.assertNotEqual(os.stat(self.dir).st_mode, self.dstat)

	def test_link1(self):
		file_, link = self.files[0], self.links[0]

		sh.chmod(link, 0644)
		self.assertNotEqual(os.stat(file_).st_mode, self.fstats[0])
		self.assertEqual(get_mode(file_), 0644)
		self.assertLinkModes()

		sh.chmod(link, 0600, dereference=True)
		self.assertEqual(get_mode(file_), 0600)
		self.assertLinkModes()

	def test_link2(self):
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

	def test_merge1(self):
		sh.chmod(self.files[1], 0134, merge=True)
		self.assertEqual(get_mode(self.files[1]), 0774)

	def test_merge2(self):
		sh.chmod(self.files[1], 0660, merge=True)
		self.assertEqual(get_mode(self.files[1]), 0660)

	def test_merge_link(self):
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
	def test_super(self):
		file_, dir_ = self.files[0], self.dir
		sh.chmod(file_, 04700)
		self.assertEqual(get_mode(file_), 04700)
		sh.chmod(dir_, 02700, merge=True)
		self.assertEqual(get_mode(dir_), 02750)
		sh.chmod(dir_, 03000, merge=True)
		self.assertEqual(get_mode(dir_), 03750)



class SH_TestChown(SH_TestFilesMacro):

	@skipUnlessUids()
	def test_exc(self, uname, gname, uid, gid):
		nxname = getnxname()
		with self.assertRaises(OSError): sh.chown(self.nxfile, uid, gid)
		with self.assertRaises(KeyError): sh.chown(self.files[0], nxname, None)
		with self.assertRaises(KeyError): sh.chown(self.files[0], None, nxname)
		os.setegid(gid), os.seteuid(uid)
		with self.assertRaises(OSError): sh.chown(self.files[0], 0, gid)

	@skipUnlessUids()
	def test_simple(self, uname, gname, uid, gid):
		file_, chk = self.files[0], self.assertIDs
		os.lchown(file_, 0, 0)

		sh.chown(file_, uid, gid), chk(uid, gid, file_)
		sh.chown(file_, uid=0, gid=0), chk(0, 0, file_)
		sh.chown(file_, uid=uid), chk(uid, 0, file_)
		sh.chown(file_, 0), chk(0, 0, file_)
		sh.chown(file_, gid=gid), chk(0, gid, file_)
		sh.chown(file_, uid, -1), chk(uid, gid, file_)
		sh.chown(file_, -1, 0), chk(uid, 0, file_)
		sh.chown(file_, -1, -1), chk(uid, 0, file_)
		sh.chown(file_, None, None), chk(uid, 0, file_)
		sh.chown(file_, None, gid), chk(uid, gid, file_)
		sh.chown(file_, 0, None), chk(0, gid, file_)
		sh.chown(file_, 0, 0), chk(0, 0, file_)
		sh.chown(file_, uname, gname), chk(uid, gid, file_)

		os.lchown(self.links[0], uid, gid)
		sh.chown(self.links[0], 0, 0, dereference=False)
		chk(uid, gid, file_), chk(0, 0, self.links[0])

	@skipUnlessUids()
	def test_recursive(self, uname, gname, uid, gid):
		dir_, dir_link, chk = self.dir, self.dir_link, self.assertIDs
		file_, link, link_file = self.tmp_dir_idx['h1']['file'],\
			self.tmp_dir_idx['h1']['h12']['link_l0'], self.tmp_dir_idx['file_l0']
		os.lchown(dir_link, uid, gid), os.lchown(link, uid, gid)
		os.chown(dir_, uid, gid), os.chown(file_, uid, gid), os.chown(link_file, uid, gid)

		sh.chown(dir_link, 0, 0, dereference=False)
		chk(uid, gid, file_, dir_), chk(0, 0, dir_link)

		sh.chown(dir_link, 0, gid, dereference=False, recursive=True)
		chk(0, gid, dir_link), chk(uid, gid, dir_, file_, link, link_file)
		sh.chown(dir_, 0, gid, dereference=False, recursive=True)

		# Recursive link should produce endless loop on dereference
		os.remove(self.tmp_dir_idx['h1']['h12']['link_d2'])

		sh.chown(dir_link, 0, 0, recursive=True)
		chk(0, 0, dir_, file_, dir_link, link, link_file)
		sh.chown(dir_link, uid, 0, dereference=True, recursive=True)
		chk(uid, 0, dir_, file_, dir_link, link, link_file)



class SH_TestCpData(SH_TestFilesMacro):

	def test_exc(self):
		with self.assertRaises((IOError, OSError)):
			sh.cp_data(self.nxfile, self.files[1])

	def test_samefile(self):
		with self.assertRaises(sh.Error): sh.cp_data(self.files[0], self.links[0])
		with self.assertRaises(sh.Error): sh.cp_data(*self.hl)
		self.assertFileModes()
		self.assertFileContents()

	def test_simple(self):
		sh.cp_data(*self.files)
		self.assertFileModes()
		self.assertContentsEqual()

	def test_links1(self):
		sh.cp_data(*self.links)
		self.assertLinkModes()
		self.assertLinkTargets()
		self.assertContentsEqual()

	def test_links2(self):
		sh.cp_data(self.links[0], self.files[1])
		self.assertLinkModes()
		self.assertLinkTargets()
		self.assertFileModes()
		self.assertContentsEqual()

	def test_append(self):
		sh.cp_data(*self.files, append=True)
		self.assertEqual(self.contents[1] + self.contents[0], open(self.files[1], 'rb').read())



# There's just no standard substitute for this
try: from os_ext import lutimes
except ImportError: lutimes = False

class SH_TestCpMacro(SH_TestFilesMacro):

	def setUp(self, stats=True):
		super(SH_TestCpMacro, self).setUp(stats=False)
		self.dirs = self.dir, unicode(self.tmp_dir_idx['files'])
		self.dir_links = self.dir_link, self.tmp_dir_idx['h1']['h11']['link_d1']

		self.dst = self.tmp_dir_idx.node('dst')
		self.dst_dir = unicode(self.tmp_dir_idx['files'])
		self.dst_dir_node = os.path.join(self.dst_dir, os.path.basename(self.files[0]))

		if hasattr(os, 'lchmod'):
			for link in self.links: os.lchmod(link, 777)
		self.assertModesEqual(*self.links)

		if stats: self.setUpStats()

		# Times are affected by subsequent stat's, so they have to be set last
		ts = time()
		self.file_times = (ts - 300, ts - 500), (ts, ts)
		for file_, times in it.izip(self.files, self.file_times): os.utime(file_, times)

		self.dir_times = (ts - 500, ts - 900), (ts - 600, ts - 1000)
		for dir_, times in it.izip(self.dirs, self.dir_times): os.utime(dir_, times)

		if lutimes:
			self.link_times = (ts - 900, ts - 1300), (ts - 1000, ts - 1400)
			for link, times in it.izip(self.links, self.link_times): lutimes(link, times)
			self.dl_times = (ts - 700, ts - 1100), (ts - 800, ts - 1200)
			for link, times in it.izip(self.dir_links, self.dl_times): lutimes(link, times)


	def assertFileTimesEqual(self, *paths, **kwz):
		if not paths: paths = self.files
		if 'times' not in kwz: kwz['times'] = self.file_times[0]
		self.assertTimesEqual(*paths, **kwz)
	def assertFileTimesNotEqual(self, *paths, **kwz):
		if not paths: paths = self.files if 'times' in kwz else self.files[1:]
		if 'times' not in kwz: kwz['times'] = self.file_times[0]
		if 'func' not in kwz: kwz['func'] = self.assertNotAlmostEqual
		self.assertFileTimesEqual(*paths, **kwz)


	def _chown_nodes(self, uid, gid): # for privileged tests
		os.chown(self.files[0], uid, gid), os.chown(self.files[1], 0, 0)
		self.assertFileModes()
		os.lchown(self.links[0], uid, 0), os.lchown(self.links[1], 0, gid)
		if hasattr(os, 'lchmod'):
			os.lchmod(self.links[0], 0751), os.lchmod(self.links[1], 0700)
			self.lstats = tuple(os.lstat(path).st_mode for path in self.links)
		for file_, times in it.izip(self.files, self.file_times): os.utime(file_, times)
		if lutimes:
			for link, times in it.izip(self.links, self.link_times): lutimes(link, times)



class SH_TestCpMeta(SH_TestCpMacro):

	def test_ts1(self):
		sh.cp_meta(*self.files)
		self.assertFileTimesNotEqual()
		self.assertFileModesEqual()
		self.assertFileContents()

	# def test_ts2(self):
	# 	sh.cp_meta(*self.files, skip_ts=True)
	# 	self.assertFileTimesNotEqual()
	# 	self.assertFileModesEqual()
	# 	self.assertFileContents()

	def test_ts3(self):
		sh.cp_meta(*self.files, skip_ts=False)
		self.assertFileTimesEqual()
		self.assertFileModesEqual()
		self.assertFileContents()

	def test_exc(self):
		with self.assertRaises((IOError, OSError)):
			sh.cp_meta(self.nxfile, self.files[1])
		with self.assertRaises((IOError, OSError)):
			sh.cp_meta(self.files[0], self.nxfile)

	def test_stat(self):
		sh.cp_meta(os.stat(self.files[0]), self.files[1])
		self.assertFileTimesNotEqual()
		self.assertFileModesEqual()
		self.assertFileContents()

	def test_types(self):
		sh.cp_meta(self.files[0], self.dir, skip_ts=False)
		self.assertFileTimesEqual(self.files[0], self.dir)
		self.assertModesEqual(self.files[0], self.dir, stat_func=get_mode)
		self.assertFileContents()

	def test_dirs(self):
		sh.cp_meta(*self.dirs, skip_ts=False)
		self.assertTimesEqual(*self.dirs, times=self.dir_times[0])
		self.assertModesEqual(*self.dirs, mode=self.dstat)

	def test_return(self):
		chk, ret = os.stat(self.files[0]), sh.cp_meta(*self.files)
		self.assertEqual(type(chk), type(ret))
		self.assertEqual(chk.st_dev, ret.st_dev)
		self.assertEqual(chk.st_ino, ret.st_ino)

	def test_links1(self):
		sh.cp_meta(self.files[0], self.links[1], skip_ts=False)
		self.assertFileTimesEqual()
		if lutimes: self.assertTimesNotEqual(self.files[0], self.links[1])
		self.assertModesNotEqual(self.files[0], self.links[1], stat_func=get_mode)
		self.assertFileModesEqual(*self.files)
		self.assertModesEqual(*self.links, mode=self.lstats[0])
		self.assertFileContents()

	def test_links2(self):
		sh.cp_meta(*self.links, dereference=True, skip_ts=False)
		self.assertFileTimesEqual()
		if lutimes: self.assertTimesNotEqual(*self.links, atime_check=False)
		self.assertFileModesEqual(*self.files)
		self.assertModesEqual(*self.links, mode=self.lstats[0])
		self.assertFileContents()

	def test_links3(self):
		sh.cp_meta(*self.links, dereference=False, skip_ts=False)
		self.assertTimesNotEqual(*self.files)
		if lutimes: self.assertTimesEqual(*self.links, times=self.link_times[0])
		self.assertModesNotEqual(self.files[0], self.links[1], stat_func=get_mode)
		self.assertModesNotEqual(*self.files)
		self.assertModesEqual(*self.links)
		self.assertFileContents()

	def test_links4(self):
		if hasattr(os, 'lchmod'):
			os.lchmod(self.links[1], 700)
			sh.cp_meta(*self.links, dereference=False, skip_ts=False)
			if lutimes: self.assertTimesEqual(*self.links, times=self.link_times[0])
			self.assertModesEqual(*self.links)
		else:
			sh.cp_meta(self.files[0], self.links[1], dereference=False, skip_ts=False)
			if lutimes: self.assertTimesEqual(self.files[0], self.links[1])
			self.assertModesEqual(self.links[1], mode=self.lstats[1])
		self.assertFileContents()

	@unittest.skipUnless( lutimes,
		'os_ext.lutimes function is inaccessible - no way to set link timestamps' )
	def test_links4(self):
		sh.cp_meta(*self.links, dereference=False)
		self.assertModesEqual(*self.links)
		self.assertTimesNotEqual(*self.links)
		self.assertFileContents()

	@skipUnlessUids()
	def test_exc_super(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		os.setegid(gid), os.seteuid(uid)
		with self.assertRaises((IOError, OSError)): sh.cp_meta(*self.files)

	@skipUnlessUids()
	def test_attrz1(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		sh.cp_meta(*self.files, attrz=True)
		self.assertFileTimesEqual()
		self.assertFileModesEqual()
		self.assertIDs(uid, gid, *self.files)
		self.assertFileContents()

	@skipUnlessUids()
	def test_attrz2(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		sh.cp_meta(*self.links, attrz=True)
		if lutimes: self.assertTimesNotEqual(*self.links, atime_check=False)
		if hasattr(os, 'lchmod'): self.assertModesNotEqual(*self.links)
		self.assertFileTimesEqual()
		self.assertIDs(uid, gid, *self.files)
		self.assertFileModesEqual()
		self.assertFileContents()

	@skipUnlessUids()
	def test_attrz3(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		sh.cp_meta(*self.links, dereference=True, attrz=True)
		if lutimes: self.assertTimesNotEqual(*self.links, atime_check=False)
		if hasattr(os, 'lchmod'): self.assertModesNotEqual(*self.links)
		self.assertFileTimesEqual()
		self.assertIDs(uid, gid, *self.files)
		self.assertFileModesEqual()
		self.assertFileContents()

	@skipUnlessUids()
	def test_attrz_stat(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		sh.cp_meta(os.stat(self.files[0]), self.files[1], attrz=True)
		self.assertFileTimesEqual()
		self.assertFileModesEqual()
		self.assertIDs(uid, gid, *self.files)
		self.assertFileContents()

	@skipUnlessUids()
	def test_attrz_links1(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		sh.cp_meta(*self.links, dereference=False, attrz=True)
		if lutimes: self.assertTimesEqual(*self.links)
		self.assertModesEqual(*self.links)
		self.assertFileTimesNotEqual()
		self.assertIDs(uid, gid, self.files[0])
		self.assertIDs(0, 0, self.files[1])
		self.assertFileModes()
		self.assertFileContents()

	@skipUnlessUids()
	def test_attrz_links2(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		dir_file = self.tmp_dir_idx['h1']['file']
		os.chown(dir_file, 0, gid)
		sh.cp_meta(self.links[0], self.dir, dereference=False, attrz=True)
		if lutimes: self.assertTimesEqual(self.links[0], self.dir)
		self.assertModesEqual(self.links[0], self.dir, stat_func=get_mode)
		self.assertTimesNotEqual(self.files[0], self.dir)
		self.assertIDs(uid, 0, self.links[0], self.dir)
		self.assertIDs(0, gid, dir_file)
		self.assertFileModes()

	@skipUnlessUids()
	def test_attrz_links3(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		sh.cp_meta(self.files[0], self.links[1], dereference=False, attrz=True)
		if lutimes: self.assertTimesEqual(self.files[0], self.links[1])
		if hasattr(os, 'lchmod'): self.assertModesEqual(self.files[0], self.links[1], stat_func=get_mode)
		else: self.assertModes(self.lstats[1], self.links[1])
		self.assertTimesNotEqual(self.links[1], self.files[1], atime_check=False)
		self.assertIDs(uid, gid, self.files[0], self.links[1])
		self.assertFileModes()



class SH_TestCp(SH_TestCpMacro):

	def test_simple(self):
		sh.cp(self.files[0], self.dst)
		self.assertTimesNotEqual(self.files[0], self.dst, atime_check=False)
		self.assertModesEqual(self.files[0], self.dst)
		self.assertContentsEqual(self.files[0], self.dst)

	def test_dir(self):
		with self.assertRaises((IOError, OSError)): sh.cp(self.dirs[0], self.dst)

	def test_into(self):
		sh.cp(self.files[0], self.dst_dir)
		self.assertTimesNotEqual(self.files[0], self.dst_dir_node, atime_check=False)
		self.assertFileModesEqual(self.files[0], self.dst_dir_node)
		self.assertContentsEqual(self.files[0], self.dst_dir_node)

	def test_exc(self):
		with self.assertRaises((IOError, OSError)):
			sh.cp(self.nxfile, self.files[1])
		os.mkfifo(self.nxfile)
		with self.assertRaises(sh.Error):
			sh.cp(self.nxfile, self.files[1])

	def test_ts1(self):
		self.files = self.files[0], self.dst
		sh.cp(*self.files)
		self.assertFileTimesNotEqual()
		self.assertFileModesEqual()
		self.assertContentsEqual()

	def test_ts2(self):
		self.files = self.files[0], self.dst
		sh.cp(*self.files, skip_ts=False)
		self.assertFileTimesEqual(atime_check=False)
		self.assertFileModesEqual()
		self.assertContentsEqual()

	def test_return(self):
		self.files = self.files[0], self.dst
		chk, ret = os.stat(self.files[0]), sh.cp(*self.files)
		self.assertEqual(type(chk), type(ret))
		self.assertEqual(chk.st_dev, ret.st_dev)
		self.assertEqual(chk.st_ino, ret.st_ino)

	@skipUnlessUids()
	def test_attrz(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		self.files = self.files[0], self.dst
		sh.cp(*self.files, attrz=True)
		self.assertFileTimesEqual(atime_check=False)
		self.assertFileModesEqual()
		self.assertIDs(uid, gid, *self.files)
		self.assertContentsEqual()



class SH_TestCpVariants(SH_TestCpMacro):

	@skipUnlessUids()
	def test_cp_p(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		self.files = self.files[0], self.dst
		sh.cp_p(*self.files)
		self.assertFileTimesEqual(atime_check=False)
		self.assertFileModesEqual()
		self.assertIDs(uid, gid, *self.files)
		self.assertContentsEqual()

	def test_cp_p_return(self):
		self.files = self.files[0], self.dst
		chk, ret = os.stat(self.files[0]), sh.cp_p(*self.files)
		self.assertEqual(type(chk), type(ret))
		self.assertEqual(chk.st_dev, ret.st_dev)
		self.assertEqual(chk.st_ino, ret.st_ino)

	def test_cp_d_file(self):
		sh.cp_d(self.files[0], self.dst)
		self.assertModesEqual(self.files[0], self.dst)
		self.assertContentsEqual(self.files[0], self.dst)
	def test_cp_d_dir(self):
		sh.cp_d(self.dirs[0], self.dst)
		self.assertModesEqual(self.dirs[0], self.dst)
	def test_cp_d_link1(self):
		sh.cp_d(self.links[0], self.dst)
		self.assertModesEqual(self.files[0], self.dst)
		self.assertContentsEqual(self.files[0], self.dst)
	def test_cp_d_link2(self):
		sh.cp_d(self.links[0], self.dst, dereference=False)
		self.assertModesEqual(self.links[0], self.dst)
		self.assertTrue(os.path.samefile(self.links[0], self.dst))

	@skipUnlessUids()
	def test_cp_d_file_super(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		self.files = self.files[0], self.dst
		sh.cp_d(self.files[0], self.dst, attrz=True, dereference=False, sync=False, skip_ts=True)
		self.assertFileTimesNotEqual(atime_check=False)
		self.assertFileModesEqual()
		self.assertIDs(uid, gid, *self.files)
		self.assertContentsEqual()

	@skipUnlessUids()
	def test_cp_d_dir_super(self, uname, gname, uid, gid):
		os.chown(self.dirs[0], 0, gid)
		sh.cp_d(self.dirs[0], self.dst, attrz=True)
		self.assertModesEqual(self.dirs[0], self.dst)
		self.assertIDs(0, gid, self.dirs[0], self.dst)

	@skipUnlessUids()
	def test_cp_d_link_super(self, uname, gname, uid, gid):
		self._chown_nodes(uid, gid)
		sh.cp_d(self.links[0], self.dst, attrz=True, dereference=False)
		self.assertModesEqual(self.links[0], self.dst)
		self.assertIDs(uid, 0, self.links[0], self.dst)
		self.assertTrue(os.path.samefile(self.links[0], self.dst))


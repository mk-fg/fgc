import unittest, os, dta, string, re, sys
from fgc import sh

class SH(unittest.TestCase):
	'''
	File/dir ops test

	Not covered:
	- onerror callbacks
	- uid / gid operations
	'''

	pg = '/tmp/'+dta.uid(8, charz=string.hexdigits+' '*5)
	c = dta.uid(3, charz=string.printable+string.whitespace*7)

	def _(self, *argz):
		path = None
		while not path or os.path.exists(path):
			path = os.path.join(
				self.pg,
				*(
					argz +
					(dta.uid(8, charz=string.hexdigits+' '*5+'."!'),)
				)
			)
		return path

	def _f(self, *argz):
		path = self._(*argz)
		open(path, 'wb').write(self.c)
		return path
	def _d(self, *argz):
		path = self._(*argz)
		os.mkdir(path)
		return path

	def setUp(self):
		os.mkdir(self.pg)
		# core path w/ file & dir
		self.f1 = self._f()
		# path
		self.d1 = self._d()
		self.f2 = self._f(self.d1)
		# empty subpath
		self.d2 = self._d(self.d1)
		# subpath w/ file
		self.d3 = self._d(self.d1)
		self.f3 = self._f(self.d3)
		self.f4 = self._f(self.d3)
		# subpath w/ file 2
		self.d4 = self._d(self.d1)
		self.f5 = self._f(self.d4)
		# symlink to f3 in d1
		self.l1 = self._(self.d1)
		os.symlink(self.f3, self.l1)

	def tearDown(self):
		os.system("/bin/rm -Rf --one-file-system '%s'"%self.pg)

	def test_cat(self):
		dst = self._f()
		sh.cat(open(self.f1), open(dst, 'wb'))
		self.assertEqual(open(self.f1).read(), open(dst).read())

	def test_cmp(self):
		dst = self._()
		os.link(self.f1, dst)
		self.assertTrue(sh._cmp(self.f1, dst))

		dst = self._()
		os.symlink(self.f1, dst)
		self.assertTrue(sh._cmp(self.f1, dst))

		dst = self._()
		os.symlink(self.d1, dst)
		dst = os.path.join(dst, os.path.basename(self.f2))
		self.assertTrue(sh._cmp(self.f2, dst))

	def test_cp_files(self):
		dst = self._()
		open(dst, 'wb').write(dta.uid(16))
		os.chmod(dst, 0700)
		sample_mode = os.stat(dst).st_mode
		sh.cp_cat(self.f1, dst) # Stream cp
		self.assertEqual(open(self.f1).read(), open(dst).read())
		self.assertEqual(sample_mode, os.stat(dst).st_mode)

		src = dst
		dst = self._()
		open(dst, 'wb').write(dta.uid(16))
		sh.cp(src, dst) # Simple cp
		self.assertEqual(open(src).read(), open(dst).read())
		self.assertEqual(sample_mode, os.stat(dst).st_mode)

		self.assertRaises(sh.Error, sh.cp, self.d1, dst) # cp dir

		sh.cp(dst, self.d1) # File to dir
		self.assertEqual(
			open(os.path.join(
				self.d1,
				os.path.basename(dst)
			)).read(),
			open(dst).read()
		)

	def test_cp_recursive(self):
		dst = self._()
		sh.cp_r(self.f1, dst) # File
		self.assertEqual(open(self.f1).read(), open(dst).read())

		dst = self._()
		os.chmod(self.d1, 0750)
		os.chmod(self.f2, 0771)
		mode_l1f = os.stat(self.l1).st_mode
		try:
			os.lchmod(self.l1, 0642) # Py 2.6 only
			mode_l1 = os.lstat(self.l1).st_mode
			lchmod = True
		except AttributeError: lchmod = False
		mode_d1 = os.stat(self.d1).st_mode
		mode_f2 = os.stat(self.f2).st_mode
		sh.cp_r(self.d1, dst) # Dir
		self.assertTrue(os.path.isdir(dst)) # Dir copied
		self.assertEqual(mode_d1, os.stat(dst).st_mode) # Dir mode copied
		dst_file = os.path.join(dst, os.path.basename(self.f2))
		self.assertEqual(open(self.f2).read(), open(dst_file).read()) # File inside copied
		self.assertEqual(mode_f2, os.stat(dst_file).st_mode) # File mode copied
		dst_dir = os.path.join(dst, os.path.basename(self.d2))
		self.assertTrue(os.path.isdir(dst_dir)) # Dir copied
		dst_subfile = os.path.join(dst, os.path.basename(self.d3), os.path.basename(self.f3))
		self.assertTrue(os.path.isfile(dst_subfile)) # File inside path is copied as well
		dst_link = os.path.join(dst, os.path.basename(self.l1))
		self.assertTrue(os.path.isfile(dst_link)) # Symlink cloned as file
		self.assertEqual(open(self.l1).read(), open(dst_link).read()) # Symlink contents preserved
		self.assertEqual(mode_l1f, os.stat(dst_link).st_mode) # Symlink target mode preserved
		if lchmod:
			self.assertEqual(mode_l1, os.lstat(dst_link).st_mode) # Symlink mode copied

		dst = self._()
		dst_dupe = os.path.basename(self.f3)
		dst_skip1 = os.path.join(
			os.path.basename(self.d3),
			os.path.basename(self.f4)
		)
		dst_skip2 = os.path.basename(self.d4)
		skip = (
			'^'+re.escape(dst_dupe), # 1. File should not be skipped, since it's in d3
			'^'+re.escape(dst_skip1), # 2. File should be skipped
			'^'+re.escape(dst_skip2) # 3. Path should be skipped
		)
		sh.cp_r(self.d1, dst, symlinks=True, skip=skip) # Symlinks preservation and skip pattern

		self.assertTrue(os.path.isfile(os.path.join(
			dst,
			os.path.basename(self.d3),
			os.path.basename(self.f3)
		))) # File copied
		self.assertFalse(os.path.exists(dst_skip1)) # File skipped
		self.assertFalse(os.path.exists(dst_skip2)) # Dir skipped

		dst_link = os.path.join(dst, os.path.basename(self.l1))
		self.assertTrue(os.path.islink(dst_link)) # Symlink cloned as link
		self.assertTrue(os.path.samefile(self.l1, dst_link))
		self.assertTrue(os.path.samefile(self.f3, dst_link)) # Symlink target preserved

		self.assertRaises(sh.Error, sh.cp_r, self.d1, self.d2) # dir to existing dir


	def test_cp_defered(self):
		dst = self._()
		os.chmod(self.f1, 0604)
		sample_mode = os.stat(self.f1).st_mode
		sh.cp_d(self.f1, dst)
		self.assertTrue(os.path.isfile(dst)) # File copied
		self.assertEqual(open(self.f1).read(), open(dst).read()) # File contents preserved
		self.assertEqual(sample_mode, os.stat(dst).st_mode) # File mode preserved

		dst = self._()
		sh.cp_d(self.d1, dst)
		self.assertTrue(os.path.isdir(dst)) # Dir copied
		self.assertFalse(os.path.exists(os.path.join(
			dst,
			os.path.basename(self.f2)
		))) # ...and file isn't

		dst = self._()
		try:
			mode_l1f = os.stat(self.l1).st_mode
			os.lchmod(self.l1, 0642) # Py 2.6 only
		except AttributeError: lchmod = False
		else:
			mode_l1 = os.lstat(self.l1).st_mode
			lchmod = True
		sh.cp_d(self.l1, dst, symlinks=True)
		self.assertTrue(os.path.islink(dst)) # Link copied
		self.assertTrue(os.path.samefile(self.l1, dst)) # Link target preserved
		if lchmod:
			self.assertEqual(mode_l1, os.lstat(dst).st_mode) # Symlink mode copied
			self.assertEqual(mode_l1f, os.stat(dst).st_mode) # Symlink file mode preserved


	def test_cp_stat(self):
		os.chmod(self.f1, 0640)
		os.chmod(self.f2, 0755)
		mode_f1 = os.stat(self.f1).st_mode
		sh.cp_stat(self.f1, self.f2)
		self.assertEqual(mode_f1, os.stat(self.f2).st_mode) # File mode cloned
		self.assertEqual(mode_f1, os.stat(self.f1).st_mode) # Original file mode preserved
		os.chmod(self.f2, 0755)
		sh.cp_stat(self.f1, self.f2, deference=True)
		self.assertEqual(mode_f1, os.stat(self.f2).st_mode) # File mode cloned anyway

		mode_d1 = os.stat(self.d1).st_mode
		os.chmod(self.d1, 0750)
		sh.cp_stat(self.d1, self.d2, deference=True)
		self.assertEqual(mode_f1, os.stat(self.f2).st_mode) # File mode cloned

		os.chmod(self.l1, 0644)
		sh.cp_stat(self.l1, self.f2, deference=True)
		self.assertEqual(os.stat(self.l1).st_mode, os.stat(self.f2).st_mode) # File mode cloned

		try: os.lchmod(self.l1, 0642) # Py 2.6 only
		except AttributeError: pass
		else:
			sh.cp_stat(self.l1, self.f2, deference=False)
			self.assertEqual(os.lstat(self.l1).st_mode, os.stat(self.f2).st_mode) # Link mode cloned


	def test_rm(self):
		sh.rm(self.f1)
		self.assertFalse(os.path.exists(self.f1)) # File removed
		sh.rm(self.l1)
		self.assertFalse(os.path.exists(self.l1)) # Link removed
		self.assertTrue(os.path.exists(self.f3)) # Check for collateral damage (link target)
		sh.rm(self.d2)
		self.assertFalse(os.path.exists(self.d2)) # Empty dir removed
		self.assertRaises(sh.Error, sh.rm, self.d1) # Non-empty dir


	def test_rr(self):
		sh.rr(self.f1)
		self.assertFalse(os.path.exists(self.f1)) # File removed
		sh.rr(self.l1)
		self.assertFalse(os.path.exists(self.l1)) # Link removed
		self.assertTrue(os.path.exists(self.f3)) # Check for collateral damage (link target)
		sh.rr(self.d4)
		self.assertFalse(os.path.exists(self.d4)) # Dir removed

		skip = (
			'^'+re.escape(os.path.join(
				os.path.basename(self.d3),
				os.path.basename(self.f3)
			)), # 1. File should not be removed
			'^'+re.escape(os.path.basename(self.f4)), # 2. File should be removed, since it's really in d3
			'^'+re.escape(os.path.basename(self.d2)) # 3. Path should be skipped
		)
		sh.rr(self.d1, preserve=skip)
		self.assertTrue(os.path.exists(self.f3)) # 1
		self.assertFalse(os.path.exists(self.f4)) # 2
		self.assertTrue(os.path.exists(self.d2)) # 3
		sh.rr(self.d2, keep_root=True)
		self.assertTrue(os.path.exists(self.d2)) # Root should be intact



	def test_mv_basic(self):
		dst = self._()
		cache = open(self.f1).read()
		sh.mv(self.f1, dst) # File
		self.assertEqual(cache, open(dst).read())
		self.assertFalse(os.path.exists(self.f1))

		dst = self._()
		os.chmod(self.d1, 0750)
		os.chmod(self.f2, 0771)
		mode_l1f = os.stat(self.l1).st_mode
		try:
			os.lchmod(self.l1, 0642) # Py 2.6 only
			mode_l1 = os.lstat(self.l1).st_mode
			lchmod = True
		except AttributeError: lchmod = False
		mode_d1 = os.stat(self.d1).st_mode
		mode_f2 = os.stat(self.f2).st_mode
		cache_f2 = open(self.f2).read()
		sh.mv(self.d1, dst) # Dir
		self.assertTrue(os.path.isdir(dst)) # Dir moved
		self.assertEqual(mode_d1, os.stat(dst).st_mode) # Dir mode copied
		dst_file = os.path.join(dst, os.path.basename(self.f2))
		self.assertEqual(cache_f2, open(dst_file).read()) # File inside copied
		self.assertEqual(mode_f2, os.stat(dst_file).st_mode) # File mode copied
		dst_dir = os.path.join(dst, os.path.basename(self.d2))
		self.assertTrue(os.path.isdir(dst_dir)) # Dir copied
		dst_subfile = os.path.join(dst, os.path.basename(self.d3), os.path.basename(self.f3))
		self.assertTrue(os.path.isfile(dst_subfile)) # File inside path is moved as well
		dst_link = os.path.join(dst, os.path.basename(self.l1))
		self.assertTrue(os.path.islink(dst_link)) # Symlink moved correctly
		self.assertRaises(OSError, os.stat, dst_link) # Symlink target no longer exists
		if lchmod:
			self.assertEqual(mode_l1, os.lstat(dst_link).st_mode) # Symlink mode preserved


	def test_fsc(self):
		self.assertEqual(
			sorted([path for path in sh.crawl(self.d1)]),
			sorted([path.split(self.d1+'/')[1] for path in [self.d2, self.d3, self.d4, self.f2, self.f4, self.f3, self.f5, self.l1]])
		)
		self.assertEqual(
			sorted([path for path in sh.crawl(self.d1, dirs=False)]),
			sorted([path.split(self.d1+'/')[1] for path in [self.f2, self.f4, self.f3, self.f5, self.l1]])
		)
		self.assertEqual(
			sorted([path for path in sh.crawl(
				self.d1,
				filter=[
					'^'+re.escape(os.path.basename(self.d3)),
					'^'+re.escape(os.path.basename(self.d2))
				]
			)]),
			sorted([path.split(self.d1+'/')[1] for path in [self.d3, self.d2, self.f3, self.f4]])
		)


	def test_touch(self):
		dst = self._()
		mode = 0755
		os.chmod(self.f1, mode)
		sh.touch(dst, mode)
		self.assertTrue(os.path.isfile(dst)) # File was created
		self.assertEqual('', open(dst).read()) # Empty
		self.assertEqual(os.stat(self.f1).st_mode, os.stat(dst).st_mode) # Mode is correct


	def test_mkdir(self):
		dst1 = self._()
		dst2 = self._(dst1)
		mode = 0751
		os.chmod(self.d1, mode)
		sh.mkdir(dst2, mode, recursive=True)
		self.assertTrue(os.path.isdir(dst2)) # Dir was created
		self.assertEqual(os.stat(self.d1).st_mode, os.stat(dst1).st_mode)
		self.assertEqual(os.stat(self.d1).st_mode, os.stat(dst2).st_mode) # Modes are correct
		self.assertRaises(sh.Error, sh.mkdir, self.f1) # Error is raised, since path exists


	def test_ln(self):
		dst1 = self._()
		dst2 = self._(dst1)
		sh.ln(self.d1, dst2, recursive=True)
		self.assertTrue(os.path.isdir(dst1)) # Intermediate dir was created
		self.assertTrue(os.path.islink(dst2)) # Symlink was created
		self.assertEqual(self.d1, os.path.realpath(dst2)) # Symlink points to correct path

		dst = self._()
		sh.ln(self.f1, dst, hard=True, recursive=True)
		self.assertTrue(os.path.isfile(dst)) # Hardlink was created
		self.assertTrue(os.path.samefile(self.f1, dst)) # Hardlink points to the same file

		self.assertRaises(sh.Error, sh.ln, self.f1, dst) # Error is raised, since link exists


	def test_ln_r(self):
		dst = self._()
		sh.ln_r(self.d1, dst)
		self.assertTrue(os.path.isdir(dst)) # Path was cloned
		self.assertFalse(os.path.samefile(self.d1, dst)) # Path wasn't hardlinked (hardly possible, btw)
		self.assertTrue(os.path.samefile(self.f2, os.path.join(dst, os.path.basename(self.f2)))) # File inside was linked
		self.assertFalse(os.path.samefile(self.d2, os.path.join(dst, os.path.basename(self.d2)))) # Subdir wasn't linked
		self.assertRaises(sh.Error, sh.ln_r, self.f3, dst) # Error is raised, since path exists


	def test_mode(self):
		self.assertEqual(sh.mode('rwxr--r--'), 0744)
		self.assertEqual(sh.mode('rw-rw-r--'), 0664)
		self.assertEqual(sh.mode('r--------'), 0400)
		self.assertEqual(sh.mode('710'), 0710)
		self.assertEqual(sh.mode('64'), 0640)
		self.assertEqual(sh.mode('4'), 0400)


if __name__ == "__main__":
	unittest.main()


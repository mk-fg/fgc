from pyrrd.rrd import RRD as PyRRD, PyRRA, DataSource
import itertools as it, operator as op, functools as ft
from time import time
import os


def rrd_lazy_create(func):
	'Decorator to init rrd if it doesnt exists on disk prior to actual call'
	@ft.wraps(func)
	def _lazy_create(self, *argz, **kwz):
		if not os.path.exists(self.filename): self.create()
		return func(self, *argz, **kwz)
	return _lazy_create


class RRD(PyRRD):
	_pyrrd_api = None

	headers = tuple() # so they can be renamed/overidden at will
	step = 0

	def hour_rows(self, steps): return 3600 // (self.step * steps)
	def day_rows(self, steps): return (3600 * 24) // (self.step * steps)

	def __init__(self, filename=None, start=None, mode='w'):
		if not self.headers or not self.step: raise NotImplementedError
		ds, rra = self._get_structure()
		self._pyrrd_api = super(RRD, self)
		self._pyrrd_api.__init__( filename,
			step=self.step, start=start, mode=mode, ds=ds, rra=rra )


	@rrd_lazy_create
	def sync(self, template=None):
		return self._pyrrd_api.update(template=':'.join(template or self.headers))
	update = sync

	def add(self, *values, **kwz):
		return self._pyrrd_api.bufferValue(int(kwz.get('ts') or time()), *values)
	bufferValue = add


	def insert(self, *values, **kwz):
		'''High-level interface, accepting any iterables (sorted according to headers)
			as values, but w/o ability to specify value timestamp or other parameters (if there are any)'''
		for val in values: self.add(*val, ts=kwz.get('ts'))
		return self.sync(template=kwz.get('template') or self.headers)

	def insert_one(self, *cols, **kwz):
		'Thin wrapper for insert method for insertion of a single value'
		return self.insert(cols, **kwz)

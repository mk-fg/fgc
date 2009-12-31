'High-level POSIX capabilities manipulation interface'

import itertools as it, operator as op, functools as ft
from fgc import strcaps


sets_cap = ['permitted', 'inherited', 'effective']
sets_str = map(op.itemgetter(0), sets_cap)
s2c = dict(it.izip(sets_str, sets_cap)).__getitem__
c2s = dict(it.izip(sets_cap, sets_str)).__getitem__


@ft.wraps(strcaps.get_file)
def get_file(*path): return Caps(strcaps.get_file(*path))
@ft.wraps(strcaps.get_process)
def get_process(*pid): return Caps(strcaps.get_process(*pid))

@ft.wraps(strcaps.set_file)
def set_file(caps, *path): return strcaps.set_file(str(caps), *path)
@ft.wraps(strcaps.set_process)
def set_process(caps, *pid): return strcaps.set_process(str(caps), *pid)


class Caps(object):
	_caps = dict((cap, set()) for cap in sets_cap)

	from_file = staticmethod(get_file)
	from_process = staticmethod(get_process)


	def __init__(self, strcaps=''):
		for cap in strcaps.split():
			for mod in '=+-':
				try: cap, act = cap.split(mod)
				except ValueError: continue
				cap = cap.split(',')
				if mod == '=':
					if not act: self._caps = Caps._caps
					else:
						for mod in act:
							self._caps[s2c(mod)] = set(cap)
				elif mod == '+':
					for mod in act:
						self._caps[s2c(mod)].update(cap)
				elif mod == '-':
					for mod in act:
						self._caps[s2c(mod)].difference_update(cap)
				break
			else:
				raise ValueError, 'Invalid cap-spec: {0}'.format(cap)

	def __str__(self):
		# Very simple implementation w/o looking for common subsets
		strcaps = '='
		caps = self._caps.copy()
		for act in sets_cap:
			if self._caps.get(act):
				strcaps += ' {0}+{1}'.format(','.join(caps.pop(act)), c2s(act))
		caps = map(op.itemgetter(0), it.ifilter(op.itemgetter(1), caps.iteritems()))
		if caps: raise ValueError, 'Invalid cap-set(s): {0}'.format(','.join(caps))
		return strcaps
	def __repr__(self): return '<{0}#{1}: {2}>'.format(self.__class__, id(self), str(self))


	def __getattr__(self, k): return self._caps[k]
	def __setattr__(self, k, v):
		if k == '_caps': super(Caps, self).__setattr__(k, v)
		else: self._caps[k] = set(v)


	def activate(self):
		'Set all permitted caps as effective'
		self._caps['effective'] = self._caps['permitted']
		return self
	def deactivate(self):
		'Reset effective caps'
		self._caps['effective'] = set()
		return self

	def propagate(self):
		'Make all permitted caps inheritable'
		self._caps['inheritable'] = self._caps['permitted']
		return self
	def terminate(self):
		'Drop inheritable caps'
		self._caps['inheritable'] = set()
		return self

	def clear(self):
		'Strip all caps'
		self._caps = Caps._caps
		return self


	def apply(self, *dst):
		if not dst: return set_process(self)
		if len(dst) > 1: raise TypeError
		else: dst = dst[0]
		return set_process(self, dst)\
			if isinstance(dst, (int, long, float)) else set_file(self, str(dst))


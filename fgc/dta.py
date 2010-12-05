from string import whitespace as spaces
from contextlib import contextmanager


import types
from collections import Mapping
types.MethodWrapperType = type(object().__hash__)

class AttrDict(dict):
	def __init__(self, *argz, **kwz):
		for k,v in dict(*argz, **kwz).iteritems(): self[k] = v

	def __setitem__(self, k, v):
		super(AttrDict, self).__setitem__( k,
			AttrDict(v) if isinstance(v, Mapping) else v )
	def __getattr__(self, k):
		if not k.startswith('__'): return self[k]
		else: raise AttributeError # necessary for stuff like __deepcopy__ or __hash__
	def __setattr__(self, k, v): self[k] = v

	@classmethod
	def _from_optz(cls, optz):
		return cls( (attr, getattr(optz, attr))
			for attr in dir(optz) if attr[0] != '_' and not isinstance( attr,
				(types.BuiltinMethodType, types.MethodType,
					types.MethodWrapperType, types.TypeType) ) )\
			if not isinstance(optz, Mapping) else cls(optz)


def chain(*argz, **kwz):
	nonempty = kwz.get('nonempty', False)
	for arg in argz:
		if nonempty and arg is None: continue
		elif isinstance(arg, (types.StringTypes, int, float)): yield arg
		else:
			try:
				for sub in arg:
					if not nonempty or not sub is None: yield sub
			except TypeError: yield arg


def coroutine(proc):
	def init(*argz,**kwz):
		cr = proc(*argz,**kwz)
		cr.next()
		return cr
	return init


_cache, _cache_func = dict(), None
def cached(proc):
	from collections import deque
	import itertools as it
	global _cache_func
	if _cache_func: return _cache_func
	else:
		def frozen(obj):
			if isinstance(obj, dict):
				return frozenset((frozen(x[0]), frozen(x[1])) for x in obj)
			if isinstance(obj, set):
				return frozenset(it.imap(frozen, obj))
			if isinstance(obj, (list, tuple, deque)):
				return tuple(it.imap(frozen, obj))
			return obj
		def _cache_func(*argz, **kwz):
			key = id(proc), frozen(argz), frozen(kwz)
			try: return _cache[key]
			except KeyError:
				result = _cache[key] = proc(*argz, **kwz)
				return result
		return _cache_func


_counters = dict()
def countdown(val, message=None, error=StopIteration):
	if not message:
		while True:
			name = uid()
			if name not in _counters: break
	else: name = message
	_counters[name] = val
	def counter():
		_counters[name] -= 1
		if _counters[name] <= 0: raise error(message or 'countdown')
	return counter

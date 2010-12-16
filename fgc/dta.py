import itertools as it, operator as op, functools as ft


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
	global _cache_func
	if not _cache_func:
		def frozen(obj):
			if isinstance(obj, dict):
				return frozenset((frozen(x[0]), frozen(x[1])) for x in obj)
			if isinstance(obj, set):
				return frozenset(it.imap(frozen, obj))
			if isinstance(obj, (list, tuple, deque)):
				return tuple(it.imap(frozen, obj))
			return obj
		def _cache_func(proc, *argz, **kwz):
			key = id(proc), frozen(argz), frozen(kwz)
			try: return _cache[key]
			except KeyError:
				result = _cache[key] = proc(*argz, **kwz)
				return result
	return ft.partial(_cache_func, proc)


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


class ProxyObject(object):
	__slots__ = '_obj', '__weakref__'
	def __init__(self, *obj):
		super(ProxyObject, self).__setattr__('_obj', obj)

	def __apply(self, func, *argz):
		for obj in super(ProxyObject, self).__getattribute__('_obj'):
			try: return func(obj, *argz)
			except AttributeError: pass
		else: raise AttributeError, argz[0]

	def __getattr__(self, name): return self.__apply(getattr, name)
	def __delattr__(self, name): return self.__apply(delattr, name)
	def __setattr__(self, name, value): return self.__apply(setattr, name, value)

	def __nonzero__(self): return self.__apply(bool)
	def __str__(self): return self.__apply(str)
	def __repr__(self): return self.__apply(repr)


_property_wrapper = lambda func, self, *argz, **kwz: func(*argz, **kwz)
def static_property(fget=None, fset=None, fdel=None, **kwz):
	'Same as property, but does not pass the self argument to functions.'
	funcs = locals()
	return property(**dict( (fn, ft.partial(_property_wrapper, funcs[fn]))
		for fn in ('fget', 'fset', 'fdel') if funcs[fn] is not None ))


def uid(length=8):
	'Returns pseudo-random string built in a simpliest way possible'
	length, cut = length // 2, length % 2
	return open('/dev/urandom', 'rb').read(length + cut).encode('hex')[:-cut or None]

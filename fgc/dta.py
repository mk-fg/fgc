from string import whitespace as spaces
from contextlib import contextmanager


import types
atomic = types.StringTypes, int, float # data types, considered uniterable



### TODO: Merge hosting.config here
do_init = lambda dta: do( (k, do_init(v)) for k,v in dta.iteritems() ) if isinstance(dta, dict) else dta

@contextmanager
def _import(path):
	try: yield __import(path)
	except Exception as ex: raise ex
def __import(path):
	def _process(cfg):
		try:
			import yaml
			return yaml.load(cfg)
		except: return json.loads(cfg)
	with open(path) as cfg:
		json_format = (cfg.readline().strip(spaces) == '{')
		cfg.seek(0)
		return _process(cfg.read().replace('\n', '') if json_format else cfg)

### TODO: Merge hosting.config here
class do(dict):
	'''DataObject - dict with JS-like key=attr access'''
	def __init__(self, *argz, **kwz):
		if len(argz) and isinstance(argz[0], atomic):
			with _import(argz[0]) as cfg: super(do, self).__init__(cfg)
			for arg in argz[1:]:
				with _import(arg) as cfg: self.update(cfg)
		else: super(do, self).__init__(*argz, **kwz)
		for k,v in self.iteritems(): self[k] = do_init(v)
	def __getattr__(self, k): return self[k]
	def __setattr__(self, k, v): dict.__setitem__(self, k, do_init(v))


def chain(*argz, **kwz):
	nonempty = kwz.get('nonempty', False)
	for arg in argz:
		if nonempty and arg is None: continue
		elif isinstance(arg, atomic): yield arg
		else:
			try:
				for sub in arg:
					if not nonempty or not sub is None: yield sub
			except TypeError: yield arg


def overlap(*argz):
	argz = list(iter(arg) for arg in argz)
	while argz:
		val = argz # to avoid bogus matches
		for arg in list(argz):
			try:
				if not val is argz: arg.next()
				else: val = arg.next()
			except StopIteration: argz.remove(arg)
		if argz: yield val # every arg could be depleted


def fchain(*procz):
	def process(*argz, **kwz):
		chain = iter(procz)
		data = chain.next()(*argz, **kwz)
		for proc in chain: data = proc(data)
		return data
	return process

def fcall(*procz):
	def process():
		for proc in procz: proc()
	return process


dmap = lambda idict, key=None, val=None: \
	((key and key(k) or k, val and val(v) or v) for k,v in idict)


def coroutine(proc):
    def init(*argz,**kwz):
        cr = proc(*argz,**kwz)
        cr.next()
        return cr
    return init


_cache = dict()
def cached(proc):
	from collections import deque
	import itertools as it

	def frozen(obj):
		if isinstance(obj, dict):
			return frozenset((frozen(x[0]), frozen(x[1])) for x in obj)
		if isinstance(obj, set):
			return frozenset(it.imap(frozen, obj))
		if isinstance(obj, (list, tuple, deque)):
			return tuple(it.imap(frozen, obj))
		return obj

	def memoize(*argz, **kwz):
		key = id(proc), frozen(argz), frozen(kwz)
		try: return _cache[key]
		except KeyError:
			result = _cache[key] = proc(*argz, **kwz)
			return result
	return memoize

memoized = cached


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


import string, random
def uid(len=8, charz=string.digits+'abcdef'):
	buff = buffer('')
	while len:
		buff += random.choice(charz)
		len -= 1
	return buff



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



## Not used yet
# from weakref import WeakValueDictionary, ref as _ref

# def ref(val):
# 	return Ptr(None, val) if isinstance( val, immutable + bimutable ) else _ref(val)

# class Ptr(namedtuple('Ptr', 'key value')):
# 	__slots__ = ()
# 	def __call__(self): return self.value

# class PtrDict(WeakValueDictionary):
# 	'''WeakValueDictionary w/ support for immutable types'''
# 	def __setitem__(self, key, value):
# 		if isinstance(value, immutable + bimutable): self.data[key] = Ptr(key, value)
# 		else: WeakValueDictionary.__setitem__(self, key, value)
# 	__str__ = lambda s: '<PtrDict: %s id:%s>'%(dict(s.iteritems()), id(s))
# 	__repr__ = lambda s: '<PtrDict %s>'%id(s)


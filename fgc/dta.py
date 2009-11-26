import itertools as it, operator as op, functools as ft
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



def frozen(obj):
	if isinstance(obj, dict):
		return frozenset((frozen(x[0]), frozen(x[1])) for x in obj)
	if isinstance(obj, set):
		return frozenset(it.imap(frozen, obj))
	if isinstance(obj, (list, tuple, collections.deque)):
		return tuple(it.imap(frozen, obj))
	return obj


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



# class BInt(object):
# 	def __init__(self, value=0, limit=1):
# 		self.value, self._liimit = value, abs(limit)

# 	@property
# 	def bounded(self):
# 		if self.value < -self._limit: self.value = -self._limit
# 		elif self.value > self._limit: self.value = self._limit
# 		return self
# 	@property
# 	def max(self): return self.value == self.limit
# 	@property
# 	def mim(self): return self.value == -self.limit

# 	def __add__(self, val):
# 		self.value += self.value
# 		return self.bounded
# 	def __sub__(self, val):
# 		self.value -= self.value
# 		return self.bounded
# 	def __nonempty__(self):
# 		return self.value != 0
# 	__bool__ = __nonempty__
# 	def __int__(self): return int(self.value)
# 	def __long__(self): return long(self.value)
# 	def __float__(self): return float(self.value)


# from time import time

# class FC_TokenBucket(object):
# 	'''Token bucket flow control mechanism implementation.

# 		Essentially it behaves like a bucket of given capacity (burst),
# 		which fills by fill_rate (flow) tokens per time unit (tick, seconds).
# 		Every poll / consume call take tokens to execute, and either
# 		block until theyre available (consume+block) or return False,
# 		if specified amount of tokens is not available.
# 		Blocking request for more tokens when bucket capacity raises an
# 		exception.

# 		tick_strangle / tick_free is a functions (or values) to set/adjust
# 		fill_rate coefficient (default: 1) in case of consequent blocks /
# 		grabs - cases when bucket fill_rate is constantly lower
# 		(non-blocking requests doesnt counts) / higher than token
# 		requests.'''

# 	_tick_mul = 1

# 	def __init__( self, flow=1, burst=5, tick=1, block=False,
# 			tick_strangle=None, tick_free=None, start=None ):
# 		'''flow: how many tokens are added per tick;
# 			burst: bucket size;
# 			tick (seconds): time unit of operation;
# 			tick_strangle / tick_free:
# 				hooks for consequent token shortage / availability,
# 				can be either int/float/long or a function, accepting
# 				current flow multiplier as a single argument;
# 			start:
# 				starting bucket size, either int/float/long or a function
# 				of bucket capacity.'''
# 		self.fill_rate = flow
# 		self.capacity = burst
# 		self._tokens = burst if start is None else self._mod(start, burst)
# 		self._tick = tick
# 		self._tick_strangle = tick_strangle
# 		self._tick_free = tick_free
# 		self._vector = BInt(limit=(1 if block else 2))
# 		self._synctime = time()

# 	_mod = lambda(s, method, val): \
# 		method if isinstance(method, (int, float, long)) else method(self._tick_mul)

# 	free = lambda s: s._tick_mul = s._mod(self._tick_free)
# 	strangle = lambda s: s._tick_mul = s._mod(self._tick_strangle)

# 	@property
# 	def tick(self): return self._tick * self._tick_mul

# 	@property
# 	def tokens(self):
# 		if self._tokens < self.capacity:
# 			ts, tick = time(), self.tick
# 			delta = self.fill_rate * (ts // tick - self._synctime // tick)
# 			self._tokens = min(self.capacity, self._tokens + delta)
# 			self._synctime = ts
# 		return self._tokens

# 	def consume(self, count=1):
# 		tc = self.tokens

# 		if count <= tc: # enough tokens are available
# 			if self._vector.max \
# 					and self._tick_free is not None: self.free()
# 			self._vector += 1
# 			self._tokens -= count
# 			return True

# 		else: # wait for tokens or lend them
# 			if block and count > self.capacity:
# 				## TODO: Implement buffered grab for this case?
# 				raise ValueError, ( 'Token bucket filter deadlock:'
# 					' %s tokens requested, while max capacity is %s'%(count, self.capacity) )
# 			if block: sleep((count - tc) * self.tick)
# 			if self._vector.min \
# 					and self._tick_strangle is not None \
# 					and (block or self._tokens > 0): self.strangle()
# 			self._vector -= 1
# 			if block: self._tokens -= count
# 			return block

# 	def poll(self, count=1):
# 		if count <= self.tokens:
# 			self._tokens -= count
# 			return True
# 		else: return False



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

from string import whitespace as spaces
from contextlib import contextmanager

atomic = str, int, float, unicode # data types, considered uniterable
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


def chain(*argz):
	for arg in argz:
		if isinstance(arg, atomic): yield arg
		else:
			try:
				for sub in arg: yield sub
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
	def process(data):
		for proc in procz: data = proc(data)
		return data
	return process


import string, random
def uid(len=8, charz=string.hexdigits):
	buff = buffer('')
	while len:
		buff += random.choice(charz)
		len -= 1
	return buff

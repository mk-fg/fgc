from string import whitespace as spaces
from contextlib import contextmanager

atomic = str, int, float, unicode # data types, considered uniterable
do_init = lambda dta: do( (k, do_init(v)) for k,v in dta.iteritems() ) if isinstance(dta, dict) else dta

@contextmanager
def _import(path):
	try: yield __import(path)
	except Exception, ex: raise ex
def __import(path):
	def _process(cfg):
		try: return yaml.load(cfg)
		except yaml.scanner.ScannerError: return json.loads(cfg)
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


from copy import deepcopy
def imap(a, b):
	try: a = a.get()
	except (AttributeError, TypeError): a = deepcopy(a)
	try: b = b.get()
	except (AttributeError, TypeError): pass
	try: b = filter(lambda x: x[0] in a, b.iteritems())
	except AttributeError: a = b
	else:
		try: a.update(b)
		except: a = b
	return a


import string, random
def uid(len=8, charz=string.hexdigits): return ''.join(random.sample(''.join(charz), len))

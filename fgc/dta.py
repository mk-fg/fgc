from datetime import datetime

def reldate(date, now = None):
	'''Returns date in easily-readable format'''
	if isinstance(date, str): date = int(date)
	if isinstance(date, (int, float)): date = datetime.fromtimestamp(date)
	if not now: now = datetime.now()
	diff = abs((date.date() - now.date()).days)
	if diff == 0: return date.strftime('%H:%M')
	elif diff == 1: return date.strftime('%H:%M, yesterday')
	elif diff < 7: return date.strftime('%H:%M, last %a').lower()
	elif diff < 14: return 'week ago'
	elif diff < 50: return '-%s weeks'%(diff/7)
	elif diff < 356: return date.strftime('%d %b')
	else: return date.strftime('%b %Y')


class do:
	'''DataObject'''
	_data = {}
	def __init__(self, *argz, **kwz):
		## TODO: Implement recursive updates (dunno what for))
		dta = dict()
		if argz:
			import yaml
			for arg in argz: dta.update(yaml.load(open(arg)))
		dta.update(kwz)
		if dta:
			self._data = dta
			for k,v in dta.iteritems(): setattr(self, k, ormap(v))
	def __repr__(self):
		return str(self.get())
	def __getitem__(self, k):
		return self.get(k)
	def get(self, key=None, y=None):
		try: data = self._data
		except AttributeError: data = self.__dict__
		try:
			if key != None: data = data[key]
		except KeyError: pass
		return data if not y else rmap(data, y)
	def set(self, k, v):
		self._data[k] = v
		setattr(self, k, ormap(v))


atomic = str, int, float, unicode

def rmap(data, y=lambda x:x, atomic=atomic):
	'''Returns data,
	with values of all iterable elements processed thru function y recursively'''
	if not isinstance(data, atomic) and data is not None:
		try: return dict([(k, rmap(v, y)) for k,v in data.iteritems()])
		except AttributeError: return [rmap(i, y) for i in data]
	else: return y(data)
def ormap(data, y=lambda x:x, atomic=atomic):
	'''Returns nested data objects,
	with values of all iterable elements processed thru function y recursively'''
	if not isinstance(data, atomic) and data is not None:
		skel = do()
		try:
			skel._data = rmap(data, y)
			for k,v in data.iteritems(): setattr(skel, k, ormap(v, y))
		except AttributeError: return [ormap(i, y) for i in data]
	else: skel = y(data) # should be 'do(...)', but not everything expects polymorphic object instead of str
	return skel


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

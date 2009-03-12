from datetime import datetime

def reldate(date, now = None):
	'''Returns date in human-readable format'''
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
	def __init__(self, **kwz):
		if kwz:
			self._data = kwz
			for k,v in kwz.iteritems(): setattr(self, k, ormap(v))
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

class cfg(do):
	'''Container class for various options'''

def rmap(data, y=lambda x:x, atomic=(str,int,unicode)):
	'''Returns data,
	with values of all iterable elements processed thru function y recursively'''
	if not isinstance(data, atomic) and data is not None:
		try: return dict([(k, rmap(v, y)) for k,v in data.iteritems()])
		except AttributeError: return [rmap(i, y) for i in data]
	else: return y(data)
def ormap(data, y=lambda x:x, atomic=(str,int,unicode)):
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


import string, random
def uid(len=8, charz=string.hexdigits):
	'''Returns random string of a specified length and pattern'''
	return ''.join(random.sample(''.join(charz), len))

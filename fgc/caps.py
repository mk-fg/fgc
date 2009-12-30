'High-level POSIX capabilities manipulation interface'

import itertools as it, operator as op, functools as ft
from fgc import strcaps


sets_cap = ['permitted', 'inherited', 'effective']
sets_str = map(op.itemgetter(0), sets_cap)
s2c = dict(it.izip(sets_str, sets_cap)).__getitem__
c2s = dict(it.izip(sets_cap, sets_str)).__getitem__


def str2caps(strcaps):
	caps = dict((cap, set()) for cap in sets_cap)
	for cap in strcaps.split():
		for mod in '=+-':
			try: cap, act = cap.split(mod)
			except ValueError: continue
			cap = cap.split(',')
			if mod == '=':
				if not act: caps = dict((cap, set()) for cap in sets_cap)
				else:
					for mod in act: caps[s2c(mod)] = set(cap)
			elif mod == '+':
				for mod in act: caps[s2c(mod)].update(cap)
			elif mod == '-':
				for mod in act: caps[s2c(mod)].difference_update(cap)
			break
		else:
			raise ValueError, 'Invalid cap-spec: {0}'.format(cap)
	return caps

def caps2str(caps):
	# Very simple implementation w/o looking for common subsets
	strcaps = '='
	for act in sets_cap:
		if act in caps:
			strcaps += ' {0}+{1}'.format(','.join(caps[act]), c2s(act))
	return strcaps


@ft.wraps(strcaps.get_file)
def get_file(*argz, **kwz): return str2caps(strcaps.get_file(*argz, **kwz))
@ft.wraps(strcaps.get_process)
def get_process(*argz, **kwz): return str2caps(strcaps.get_process(*argz, **kwz))

@ft.wraps(strcaps.set_file)
def set_file(caps, path): return strcaps.set_file(caps2str(caps), path)
@ft.wraps(strcaps.set_process)
def set_process(caps, proc=None): return strcaps.get_process(caps2str(caps), proc)

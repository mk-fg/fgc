from subprocess import Popen, PIPE


queue = []


def _(*argz, **kwz):
	'''Execute process in background'''

	try: block = kwz.pop('block')
	except KeyError: block = False

	if not argz[0][0].startswith('/'):
		try:
			import os
			from config import cfg
			argz[0][0] = os.path.join(cfg.paths.bin, argz[0][0])
		except (ImportError, AttributeError): pass

	try: cb = kwz.pop('callback')
	except KeyError: # No callback given
		if not block: queue.append(proc(*argz, **kwz))
		else: proc(*argz, **kwz).wait()
	else: # Valid callback
		if not block: queue.append((proc(*argz, **kwz), cb))
		else:
			proc(*argz, **kwz).wait()
			callback(cb)


def proc(*argz, **kwz):
	#~ if kwz.has_key('stdin') and not kwz.has_key('bufsize'): kwz['bufsize'] = 1
	return Popen(*argz, **kwz)


def wait(n=-1):
	'''
	Wait for running subprocesses to finish.
	n can be set to 0 (or None), to wait only for currently running
	processes, but not their callbacks, if any. If n is lesser than zero
	it'll run 'till all subprocesses have died.
	'''
	if not n: n = len(queue)
	while n and queue:
		proc = queue.pop(0)
		try: proc,cb = proc
		except (TypeError, ValueError): cb = None
		proc.wait()
		if cb: callback(cb)
		try: n -= 1
		except TypeError: pass



def callback(cb):
	'''
	Run callback, extracted from passed function.
	Callback will be interpreted as following:
	 - (callable, keywords), if second tuple element is dict
	 - (callable, arguments), if it's iterable
	 - (callable, argument), otherwise
	 - callable, if passed spec is not two-element iterable
	'''
	if not cb: return
	try: cb,argz = cb
	except: return cb()
	else:
		if isinstance(argz, dict): return cb(**argz)
		elif not isinstance(argz, str):
			try: return cb(*argz)
			except: pass
		return cb(argz)

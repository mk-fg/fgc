from aexec import AExec, Threader, PIPE, Time, Size, End
import os, sys, signal


queue = []
sem = None


def cap(limit):
	global sem
	if limit: sem = limit
	else: sem = None
def _sem_lock():
	global sem
	if sem == None: return
	while sem <= 0:
		for task in queue:
			try: proc,cb = task
			except (TypeError, ValueError): proc,cb = task,None
			if proc.poll() != None:
				queue.remove(task)
				callback(cb)
				break
	sem -= 1
def _sem_release():
	global sem
	try: sem += 1
	except TypeError: return


def add(*argz, **kwz): # aka 'schedule task'
	'''
	Managed task creation, which can have callback and
	 is a subject to further management via wait function.
	Any non-absolute cmd paths are subject to extension
	 relative to cfg.paths.bin parameter, if any.
	Special kwz:
		sys - simulates os.system call (but w/ solid argz and extended
		 management), implies block.
		block - blocking execution.
		callback - started or scheduled after wait call, see callback function.
		sync - synchronous (native) I/O descriptors. False is MutEx w/ sys and block.
	'''
	try: block = kwz.pop('block')
	except KeyError: block = False
	try:
		block |= kwz.pop('sys')
		kwz.update(dict(stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr))
	except KeyError: pass

	if not block: _sem_lock() # callback is mandatory in this case, to release semaphore

	if not argz[0][0].startswith('/'):
		try:
			from config import cfg
			argz[0][0] = os.path.join(cfg.paths.bin, argz[0][0])
		except (ImportError, AttributeError): pass

	try: cb = kwz.pop('callback')
	except KeyError: # no callback given
		if not block: queue.append(proc(*argz, **kwz))
		else:
			ps = proc(*argz, **kwz)
			try: return ps.wait()
			except KeyboardInterrupt, ex:
				os.kill(ps.pid, signal.SIGINT)
				ps.wait() # second SIGINT will kill python
	else: # valid callback
		if not block: queue.append((proc(*argz, **kwz), cb))
		else:
			err = proc(*argz, **kwz).wait()
			callback(cb)
			return err

_ = add # for compatibility reasons


proc = AExec
def pipe(*argz, **kwz):
	nkwz = dict(stdin=PIPE, stdout=PIPE, stderr=PIPE)
	nkwz.update(kwz)
	return proc(*argz, **nkwz)


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
		try: proc.wait()
		except OSError: pass # no child processes, dunno why it happens
		callback(cb)
		try: n -= 1
		except TypeError: pass


def callback(cb):
	'''
	Run callback, extracted from passed function.
	Callback will be interpreted as following:
		- (callable, keywords), if second element is dict
		- (callable, arguments), if it's some iterable
		- (callable, argument), otherwise
		- callable, if passed spec is not a two-element iterable
	'''
	_sem_release()
	if not cb: return
	try: cb,argz = cb
	except: return cb()
	else:
		if isinstance(argz, dict): return cb(**argz)
		elif not isinstance(argz, str):
			try: return cb(*argz)
			except TypeError: pass
		return cb(argz)

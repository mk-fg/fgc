from subprocess import Popen, PIPE
import os, sys


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
		block - blocking operation.
		callback - started or scheduled after wait call, see callback function.
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
		else: return proc(*argz, **kwz).wait()
	else: # valid callback
		if not block: queue.append((proc(*argz, **kwz), cb))
		else:
			err = proc(*argz, **kwz).wait()
			callback(cb)
			return err

_ = add # for compatibility reasons

proc = Popen
def pipe(*argz, **kwz):
	nkwz = dict(stdin=PIPE, stdout=PIPE, stderr=PIPE)
	nkwz.update(kwz)
	return proc(*argz, **nkwz)
def pin(*argz, **kwz): # pipe.stdout or "gzip < file |", if single str is given
	if not argz or not isinstance(argz[0], (tuple, list)):
		from fgc.config import cfg
		if argz: kwz['stdin'] = open(argz[0], 'rb') if isinstance(argz[0], str) else argz[0]
		argz = ([os.path.join(cfg.paths.bin, 'gzip'), '-d'],)
	return pipe(*argz, **kwz).stdout
def pout(*argz, **kwz): # pipe.stdin or "| gzip > file", if single str is given
	if not argz or not isinstance(argz[0], (tuple, list)):
		from fgc.config import cfg
		if argz: kwz['stdout'] = open(argz[0], 'wb') if isinstance(argz[0], str) else argz[0]
		argz = ([os.path.join(cfg.paths.bin, 'gzip')],)
	return pipe(*argz, **kwz).stdin


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



from threading import Thread, BoundedSemaphore
import itertools as it, operator as op, functools as ft
import Queue

class Threader(object):
	def __init__(self, process=1, results=None, timeout=5):
		self._threads = list()
		self._threads_limit = process
		if isinstance(results, int):
			results -= process
			if results <= 0: raise ValueError('Results limit must be higher than processing limit')
			self._results = Queue.Queue(results)
		elif results is None: self._results = Queue.Queue()
		else: self._results = results # custom object
		self._feed = Queue.Queue()
		self._next = ft.partial(self.get, timeout=timeout)

	def _worker(self):
		while True:
			try: idx, task = self._feed.get()
			except TypeError: # poison
				self._feed.task_done()
				break
			try: self._results.put( (idx, task()) )
			finally: self._feed.task_done() # even if task fails

	def get(self, *argz, **kwz):
		if not self._feed.unfinished_tasks and self._results.empty(): self.close(True)
		if not argz: # handle standard queue "block" argument
			try: argz = [bool(kwz['timeout'] or True)] # (timeout is 0/False) = block
			except: argz = [True]
		try: return self._results.get(*argz, **kwz) # so get can be overridden in results
		except Queue.Empty: self.close(True) # for standard results queue, in case of timeout
	def put(self, task):
		if len(self._threads) < self._threads_limit:
			thread = Thread(target=self._worker)
			thread.setDaemon(True)
			thread.start()
			self._threads.append(thread)
		self._feed.put(task)

	def _lock(self, *argz, **kwz): raise StopIteration
	def close(self, iter=False):
		self.put = self.get = self._lock # block any further I/O
		for i in xrange(len(self._threads)): self._feed.put(None) # poison all threads
		while self._threads: self._threads.pop().join(0) # collect the cadavers, if not hung
		if iter: raise StopIteration

	get_nowait = ft.partial(get, to=0)
	put_nowait = ft.partial(put, to=0)

	def __del__(self):
		if self._threads:
			for i in xrange(len(self._threads)): self._feed.put(None) # poison all threads
			while self._threads: self._threads.pop().join() # collect the cadavers

	next = lambda s: s._next()
	__iter__ = lambda s: s

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
def pin(*argz, **kwz):
	if not argz or not isinstance(argz[0], (tuple, list)):
		from hosting.config import cfg
		if argz: kwz['stdin'] = open(argz[0], 'rb') if isinstance(argz[0], str) else argz[0]
		argz = ([os.path.join(cfg.paths.bin, 'gzip'), '-d'],)
	return pipe(*argz, **kwz).stdout
def pout(*argz, **kwz):
	if not argz or not isinstance(argz[0], (tuple, list)):
		from hosting.config import cfg
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
	 - (callable, keywords), if second tuple element is dict
	 - (callable, arguments), if it's iterable
	 - (callable, argument), otherwise
	 - callable, if passed spec is not two-element iterable
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



from threading import Thread
from collections import deque
from time import sleep
from hosting import log


class Threader(object):
	_pool = None # threads count semaphore value (none - no threads)
	_threads = deque()
	_op = lambda *argz,**kwz: None # atomic operation

	def __init__(self, threads=None, cooldown=1, op=None):
		self.data = {}
		self._cooldown = cooldown # time between checks for completed queries
		if threads: self._pool = threads
		if op: self._op = op

	def _get(self, *argz,**kwz): self.data[argz[0]] = self._op(*argz,**kwz)

	def get(self, *argz,**kwz):
		try:
			self._pool -= 1
			try: # failsafe thread creation, in case of low resources
				thread = Thread(target=self._get, args=argz, kwargs=kwz)
				thread.start()
			except thread.error: self._get(*argz,**kwz)
			else: self._threads.append(thread)
			cooldown = len(self._threads)
			while self._pool < 0: # try joining some thread, starting from the oldest
				thread = self._threads.popleft()
				thread.join(0)
				if not thread.is_alive(): self._pool += 1 # gotcha!
				else: self._threads.append(thread) # push it back to queue end
				if cooldown <= 0: # all threads were probed, sleeping
					sleep(self._cooldown)
					cooldown = len(self._threads)
					log.debug('Thread queue full (%s), waiting for %ss'%(cooldown, self._cooldown))
				else: cooldown -= 1
		except:
			log.debug('Performing blocking op: %s (%s, %s)'%(self._op, argz,kwz))
			self._get(*argz,**kwz)

	def wait(self):
		while self._threads: self._threads.popleft().join()
		data = self.data
		self.data = {} # cleanup, so the object can be reused
		return data

import itertools as it, operator as op, functools as ft
from threading import Thread
import Queue


class Threader(object):
	def __init__(self, process=1, results=None, timeout=5):
		self._threads = list()
		self._threads_limit = process if process > 0 else None
		if isinstance(results, int):
			if self._threads_limit: results -= process
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
		if not self._threads_limit or len(self._threads) < self._threads_limit:
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





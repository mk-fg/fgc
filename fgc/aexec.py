import itertools as it, operator as op, functools as ft
from threading import Thread, BoundedSemaphore
import os, sys, Queue


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




from subprocess import Popen, PIPE
from select import epoll, EPOLLIN, EPOLLOUT, EPOLLERR, EPOLLHUP
import errno, fcntl
from time import time

# Exit conditions (states)
class Time: pass # hit-the-time-limit state
class Size: pass # hit-the-size-limit state
class End: pass # hit-the-end state

class AWrapper(object):
	'''Async I/O objects wrapper'''

	bs_default = 8192
	bs_max = 65536

	def __init__(self, pipe, leash=None):
		fd = self._fd = pipe.fileno()
		if leash: self.__leash = leash # fd source object, leashed here to stop gc
		self._poll_in, self._poll_out = epoll(), epoll()
		self._poll_in.register(fd, EPOLLIN | EPOLLERR | EPOLLHUP)
		self._poll_out.register(fd, EPOLLOUT | EPOLLERR | EPOLLHUP)
		self.close = pipe.close
		try: # file
			self.reads = pipe.read
			self.writes = pipe.write
		except AttributeError: # socket
			self.reads = pipe.recv
			self.writes = pipe.send

	def __del__(self):
		self._poll_in.close()
		self._poll_out.close()
		self.close()

	def read(self, bs=-1, to=-1, state=False): # read until timeout
		if to < 0: # use regular sync I/O
			buff = self.reads(bs)
			if state: return (buff, Size) if len(buff) == bs else (buff, End) # "Size" might mean "Size | End" here
			else: return buff
		try:
			flags = fcntl.fcntl(self._fd, fcntl.F_GETFL)
			fcntl.fcntl(self._fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
			deadline = time() + to
			buff = buffer('')
			while bs:
				try: fd, event = self._poll_in.poll(to, 1)[0] # get first event, fd should be eq self._fd
				except IndexError:
					if state: state = Time
					break
				if event != EPOLLHUP: # some data or error present
					ext = self.reads(min(bs, self.bs_max) if bs > 0 else self.bs_default) # min() for G+ reads
					buff += ext
				if event & EPOLLHUP: # socket is closed on the other end
					if state: state = End
					break
				to = deadline - time()
				if to < 0:
					if state: state = Time
					break
				bs -= len(ext)
			else:
				if state: state = Size # got bs bytes
		finally:
			try: fcntl.fcntl(self._fd, fcntl.F_SETFL, flags) # restore blocking state
			except: pass # in case there was an error, caused by wrong fd/pipe (not to raise another one)
		return buff if not state else (buff, state)

	def write(self, buff, to=-1, state=False): # mostly similar (in reverse) to read
		if to < 0:
			bs = self.writes(buff)
			if state: return (bs, Size) if len(buff) == bs else (bs, End) # "Size" might mean "Size | End" here
			else: return bs
		try:
			flags = fcntl.fcntl(self._fd, fcntl.F_GETFL)
			fcntl.fcntl(self._fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
			bs = 0
			deadline = time() + to
			while buff:
				try: fd, event = self._poll_out.poll(to, 1)[0]
				except IndexError:
					if state: state = Time
					break
				if event != EPOLLHUP:
					ext = os.write(fd, buff)
					bs += ext
				if event & EPOLLHUP:
					if state: state = End
					break
				to = deadline - time()
				if to < 0:
					if state: state = Time
					break
				buff = buffer(buff, ext)
		finally:
			try: fcntl.fcntl(self._fd, fcntl.F_SETFL, flags)
			except: pass
		return bs if not state else (bs, state)


class FileBridge(object):
	def __init__(self, src, leash):
		self.__src = os.fdopen(src.fileno(), src.mode)
		self.__leash = (src, leash)
	__iter__ = lambda s: iter(s.__src)
	__getattr__ = lambda s,k: getattr(s.__src,k)



import signal

class AExec(Popen):
	_ctl = None

	def __init__(self, *argz, **kwz): # keywords aren't used yet
		if len(argz) == 1:
			argz = (argz[0],) if isinstance(
				argz[0], (str, unicode, buffer)) else argz[0]
		self._cmdline = argz[0]

		try: sync = kwz.pop('sync')
		except KeyError: sync = True # yes, no async i/o by default

		try:
			if not kwz.pop('ctl'): raise KeyError
		except KeyError: child_ctl = None
		else:
			self._ctl, child_ctl = os.pipe() # control descriptor to monitor process exit
			kwz['preexec_fn'] = (lambda: os.close(self._ctl) or kwz['preexec_fn']) \
				if 'preexec_fn' in kwz else (lambda: os.close(self._ctl))

		super(AExec, self).__init__(argz, **kwz) # argz aren't expanded on purpose!

		if child_ctl: os.close(child_ctl) # close child-side control descriptor
		if kwz.get('stdin') is False and self.stdin: self.stdin.close()

		# FileBridge is necessary to stop gc from destroying other side of fd's by collecting this object
		bridge = AWrapper if not sync else FileBridge
		if self.stdin:
			self.stdin = bridge(self.stdin, self)
			self.write = self.stdin.write
		if self.stdout:
			self.stdout = bridge(self.stdout, self)
			self.read = self.stdout.read
		if self.stderr:
			self.stderr = bridge(self.stderr, self)
			self.read_err = self.stderr.read

	def fileno(self): return self._ctl

	def wait(self, to=-1):
		if to > 0:
			ts, fuse, action = time(), signal.alarm(to), signal.getsignal(signal.SIGALRM)
			def quit(s,f): raise StopIteration
			signal.signal(signal.SIGALRM, quit)
			try: status = super(AExec, self).wait()
			except StopIteration: return Time
			signal.signal(signal.SIGALRM, action)
			if fuse:
				fuse = int(time() - ts + fuse)
				if fuse > 0: signal.alarm(fuse)
				else: # trigger it immediately
					signal.alarm(0)
					os.kill(os.getpid(), signal.SIGALRM)
			else: signal.alarm(0)
		elif to == 0: status = super(AExec, self).poll()
		else: status = super(AExec, self).wait()
		return status

	def close(self, to=-1, to_sever=3):
		try:
			if self.stdin: # try to strangle it
				try: self.stdin.close()
				except: pass
				if to_sever and to > to_sever: # wait for process to die on it's own
					status = self.wait(to_sever)
					if not status is Time: return status
					else: to -= to_sever
			self.terminate() # soft-kill
			status = self.wait(to)
			if status is Time:
				self.kill() # hard-kill
				return Time
		except: return None # already taken care of
	__del__ = close

	# Helper functions
	def writeline(self, line, **kwz):
		line = str(line)
		if line[-1] != '\n': self.write(line+'\n', **kwz)
		else: self.write(line, **kwz)
		self.stdin.flush()
	def readline(self): return self.stdout.readline() # TODO: make it compatible w/ AWrapper

	def __iter__(self): return iter(self.stdout)
	def __str__(self): return '<subprocess %s: "%s">'%(self.pid, ' '.join(self._cmdline))
	__repr__ = __str__

from threading import Thread
from collections import deque
from time import sleep


class Threader:
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
				else: cooldown -= 1
		except: self._get(*argz,**kwz)

	def wait(self):
		while self._threads: self._threads.popleft().join()
		data = self.data
		self.data = {} # cleanup, so the object can be reused
		return data



from socket import gethostbyname_ex
def lookup(name):
	try: res = gethostbyname_ex(name)
	except: return None # name cannot be resolved / dns err
	else: return res[2][0]


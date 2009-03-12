from threading import BoundedSemaphore, Thread
from socket import gethostbyname_ex


class Resolver:
	_pool = None
	_threads = []
	def __init__(self, threads=None):
		if threads: self._pool = BoundedSemaphore(value=threads)
		self.data = {}
	def _lookup(self, name):
		try: res = gethostbyname_ex(name)
		except: return None
		else: return res[2][0]
	def _tlook(self, name):
		self._pool.acquire()
		self.data[name] = self._lookup(name)
		self._pool.release()
	def get(self, name):
		name = name.strip()
		if self._pool:
			thread = Thread(target=self._tlook, args=(name,))
			thread.start()
			self._threads.append(thread)
		else:
			self.data[name] = self._lookup(name)
	def block(self, name):
		return self._lookup(name)

	def wait(self):
		for thread in self._threads: thread.join()
		data = self.data
		self.data = {}
		return data

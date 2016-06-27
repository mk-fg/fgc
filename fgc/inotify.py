from collections import namedtuple, OrderedDict
import enum, struct, select, termios
import os, sys, errno, ctypes, fcntl, time


class INotify:
	# Based on inotify_simple module

	class flags(enum.IntEnum): # see "man inotify"

		access = 0x00000001
		modify = 0x00000002
		attrib = 0x00000004
		close_write = 0x00000008
		close_nowrite = 0x00000010
		open = 0x00000020
		moved_from = 0x00000040
		moved_to = 0x00000080
		create = 0x00000100
		delete = 0x00000200
		delete_self = 0x00000400
		move_self = 0x00000800

		unmount = 0x00002000
		q_overflow = 0x00004000
		ignored = 0x00008000

		onlydir = 0x01000000
		dont_follow = 0x02000000
		excl_unlink = 0x04000000
		mask_add = 0x20000000
		isdir = 0x40000000
		oneshot = 0x80000000

		close = close_write | close_nowrite
		move = moved_from | moved_to
		all_events = (
			access | modify | attrib | close_write | close_nowrite | open |
			moved_from | moved_to | delete | create | delete_self | move_self )

		@classmethod
		def unpack(cls, mask):
			return set( flag
				for flag in cls.__members__.values()
				if flag & mask == flag )

	_INotifyEv_struct = 'iIII'
	_INotifyEv_struct_len = struct.calcsize(_INotifyEv_struct)
	INotifyEv = namedtuple( 'INotifyEv',
		['path', 'path_mask', 'wd', 'flags', 'cookie', 'name'] )

	_lib = _libc = None
	@classmethod
	def _get_lib(cls):
		if cls._libc is None:
			libc = cls._libc = ctypes.CDLL('libc.so.6', use_errno=True)
		return cls._libc

	def _call(self, func, *args):
		if isinstance(func, str): func = getattr(self._lib, func)
		while True:
			res = func(*args)
			if res == -1:
				err = ctypes.get_errno()
				if err == errno.EINTR: continue
				else: raise OSError(err, os.strerror(err))
			return res

	def __init__(self):
		self._lib, self._fd = self._get_lib(), None
		self.wd_paths = OrderedDict()

	def open(self):
		self._fd = self._call('inotify_init')
		self._poller = select.epoll()
		self._poller.register(self._fd)

	def close(self):
		if self._fd:
			os.close(self._fd)
			self._fd = None
		if self._poller:
			self._poller.close()
			self._poller = None
		if self._lib: self._lib = None

	def __enter__(self):
		self.open()
		return self
	def __exit__(self, *err): self.close()
	def __del__(self): self.close()

	def add_watch(self, path, mask):
		wd = self._call('inotify_add_watch', self._fd, path.encode(), mask)
		self.wd_paths[wd] = path, mask
		return wd

	def rm_watch(self, wd):
		self._call('inotify_rm_watch', self._fd, wd)
		self.wd_paths.pop(wd)

	def poll(self, timeout=None):
		return bool(self._poller.poll(timeout))

	def read(self, poll=True, **poll_kws):
		evs = list()
		if poll:
			if not self.poll(**poll_kws): return evs
		bs = ctypes.c_int()
		fcntl.ioctl(self._fd, termios.FIONREAD, bs)
		if bs.value <= 0: return evs
		buff = os.read(self._fd, bs.value)
		n, bs = 0, len(buff)
		while n < bs:
			wd, mask, cookie, name_len = struct.unpack_from(self._INotifyEv_struct, buff, n)
			n += self._INotifyEv_struct_len
			name = ctypes.c_buffer(buff[n:n + name_len], name_len).value.decode()
			n += name_len
			evs.append(self.INotifyEv(
				*self.wd_paths[wd], wd, self.flags.unpack(mask), cookie, name ))
		return evs

	def __iter__(self):
		while True:
			for ev in self.read():
				if (yield ev) is StopIteration: break
			else: continue
			break

	@classmethod
	def ev_wait(cls, path, mask=None):
		return next(cls.ev_iter(path, mask))

	@classmethod
	def ev_iter(cls, path, mask=None):
		with cls() as ify:
			if not isinstance(path, (tuple, list)): path = [path]
			for p in path: ify.add_watch(p, mask or INotify.flags.all_events)
			ev_iter, chk = iter(ify), None
			while True:
				try: chk = yield ev_iter.send(chk)
				except StopIteration: break


if __name__ == '__main__':
	assert sys.argv[1:]
	print(INotify.ev_wait(sys.argv[1:]))

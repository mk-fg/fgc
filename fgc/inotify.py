from collections import namedtuple
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
	INotifyEv = namedtuple('INotifyEv', ['wd', 'mask', 'cookie', 'name'])

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
		return self._call('inotify_add_watch', self._fd, path.encode(), mask)
	def rm_watch(self, wd):
		return self._call('inotify_rm_watch', self._fd, wd)

	def poll(self, timeout=None):
		return bool(self._poller.poll(timeout))

	def read(self, poll=True, **poll_kws):
		if poll:
			if not self.poll(**poll_kws): return list()
		bs = ctypes.c_int()
		fcntl.ioctl(self._fd, termios.FIONREAD, bs)
		buff = os.read(self._fd, bs.value)
		n, bs, evs = 0, len(buff), list()
		while n < bs:
			wd, flags, cookie, name_len = struct.unpack_from(self._INotifyEv_struct, buff, n)
			n += self._INotifyEv_struct_len
			name = ctypes.c_buffer(buff[n:n + name_len], name_len).value.decode()
			n += name_len
			flags = self.flags.unpack(flags)
			evs.append(self.INotifyEv(wd, flags, cookie, name))
		return evs

	@classmethod
	def wait_for_event(cls, path, ev=None):
		with cls() as ify:
			ify.add_watch(path, ev or INotify.flags.all_events)
			return ify.read()

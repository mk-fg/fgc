#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools as it, operator as op
from string import whitespace as spaces
from select import epoll, EPOLLIN
from time import sleep
from fcntl import ioctl
from fgc import log
import struct, sys, os


ev_skip = set(['EV_VERSION'])

# Would be nice to cache the stuff, but cPickle sucks
#  and structures are outside JSON scope
def get_evmaps():
	type_map = EnumDict()
	code_maps = dict()

	for line in open('/usr/src/linux-2.6.30-gentoo-r4/include/linux/input.h'):
		if not line.startswith('#define'): continue
		line = line[8:] # cut '#define'
		try: event, code = line.split('\t', 1)
		except ValueError: continue # no-val defines
		if not type_map and (not event.startswith('EV_') or event in ev_skip): continue # drop pre-event defines
		code = code.lstrip(spaces).split(' ', 1)[0].split('\t', 1)[0].rstrip(spaces)
		if event.startswith('EV_'): # strip prefix for lookup convenience
			exec('%s = %s'%(event, code))
			type_map[event] = eval(event)
		else:
			ev_type = 'EV_%s'%event.split('_')[0]
			exec('%s = %s'%(event, code))
			if ev_type in type_map:
				code = eval(code)
				try: code_maps[ev_type][code] = event
				except KeyError: code_maps[ev_type] = EnumDict((code, event))

	return type_map, code_maps


class BaseDevice(object):
	'''Base class representing the state of an input device, with axes and buttons.
		Event instances can be fed into the Device to update its state.'''
	axes = dict()
	buttons = dict()
	name = None

	def __repr__(self):
		return '<Device name=%r axes=%r buttons=%r>' \
			% (self.name, self.axes, self.buttons)

	def update(self, event):
		try: getattr(self, "update_%s" % event.type)(event)
		except AttributeError: pass # no handler for event

	def __getitem__(self, name):
		'''Retrieve the current value of an axis or button,
			or zero if no data has been received for it yet.'''
		return self.axes[name] if name in self.axes else self.buttons.get(name, 0)

	def update_EV_KEY(self, event):
		self.buttons[event.code] = event.value
	def update_EV_ABS(self, event):
		self.axes[event.code] = event.value
	def update_EV_REL(self, event):
		self.axes[event.code] = self.axes.get(event.code, 0) + event.value


# evdev ioctl constants. The horrible mess here
#  is to silence silly FutureWarnings
EVIOCGNAME_512 = ~int(~0x82004506L & 0xFFFFFFFFL)
EVIOCGID = ~int(~0x80084502L & 0xFFFFFFFFL)
EVIOCGBIT_512 = ~int(~0x81fe4520L & 0xFFFFFFFFL)
EVIOCGABS_512 = ~int(~0x80144540L & 0xFFFFFFFFL)


class Device(BaseDevice):
	'''An abstract input device attached to a Linux evdev device node'''

	def __init__(self, fn):
		super(Device, self).__init__()
		self.fd = os.open(fn, os.O_RDONLY | os.O_NONBLOCK)
		self.packet_size = Event.get_format_size()
		self.read_metadata()

	def poll(self):
		'Receive and process all available input events'
		while True:
			try: buffer = os.read(self.fd, self.packet_size)
			except OSError: return
			else: self.update(Event(unpack=buffer))

	def read_metadata(self):
		'''Read device identity and capabilities via ioctl()'''
		buffer = '\0'*512

		# Read the name
		self.name = ioctl(self.fd, EVIOCGNAME_512, buffer)
		self.name = self.name[:self.name.find("\0")]

		# Read info on each absolute axis
		buffer = "\0" * struct.calcsize("iiiii")
		self.abs_axis_info = dict()
		for name, number in Event.code_maps['EV_ABS'].name_map():
			if number == 64: continue
			values = struct.unpack('iiiii', ioctl(self.fd, EVIOCGABS_512 + number, buffer))
			self.abs_axis_info[name] = dict(it.izip(( 'value', 'min', 'max', 'fuzz', 'flat' ), values))

	def update_EV_ABS(self, event):
		'''Scale the absolute axis into the range [-1, 1] using abs_axis_info'''
		try: info = self.abs_axis_info[event.code]
		except KeyError: return
		else:
			self.axes[event.code] = (event.value - info['min']) \
				/ float(info['max'] - info['min']) * 2.0 - 1.0


class DeviceGroup(object):
	'''Capture events from a group of event devices.'''

	def __init__(self, paths):
		self.reactor = epoll()
		self.devices = map(Device, paths)
		self.fds = map(op.attrgetter('fd'), self.devices)
		for fd in self.fds: self.reactor.register(fd, EPOLLIN)
		self.packet_size = Event.get_format_size()
		log.debug('DevGroup init: %r, %s'%(self, self.devices))

	def next_event(self, to=-1):
		try: fd, event = self.reactor.poll(to, 1)[0]
		except IndexError: return None # no events in a given time
		else: return Event(unpack=os.read(fd, self.packet_size))

	def flush(self): map(op.methodcaller('poll'), self.devices)

	def close(self):
		self.reactor.close()
		for fd in self.fds:
			try: os.close(fd)
			except: log.warn('failed to close one or more device fds')
	__del__ = close


class EnumDict(dict):
	'Bidirectional mapping'
	def __init__(self, *seq):
		super(EnumDict, self).__init__(seq)
		for k,v in self.items():
			if isinstance(v, (str, int)): self[v] = k
	def __setitem__(self, k, v):
		super(EnumDict, self).__setitem__(k, v)
		if isinstance(v, (str, int)): super(EnumDict, self).__setitem__(v, k)
	itermap = lambda s,t: it.ifilter(lambda x: isinstance(x[0], t), s.iteritems())
	num_map = lambda s: s.itermap(int)
	name_map = lambda s: s.itermap(str)


class Event:
	'''Represents one linux input system event. It can
		be encoded and decoded in the 'struct input_event'
		format used by the kernel. Types and codes are automatically
		encoded and decoded with the #define names used in input.h'''

	ts_format = "@LL"
	format = "=HHl"

	type_map, code_maps = get_evmaps()

	def __init__(self, timestamp=0, type=0, code=0, value=0, unpack=None, read_from=None):
		self.timestamp = timestamp
		self.type = type
		self.code = code
		self.scan_code = -1
		self.value = value
		if unpack is not None: self.unpack(unpack)
		if read_from is not None: self.read_from(read_from)

	def __repr__(self):
		return '<Event timestamp=%r type=%r code=%r value=%r>' \
			% (self.timestamp, self.type, self.code, self.value)

	@staticmethod
	def get_format_size():
		return struct.calcsize(Event.ts_format) + struct.calcsize(Event.format)

	def pack(self):
		'''Pack this event into an input_event struct in
			the local machine byte order.'''
		secs = int(self.timestamp)
		usecs = int((self.timestamp - secs) * 1000000)
		packed_type = self.type_map[self.type]
		packed_code = self.code_maps[self.type][self.code] \
			if self.type in self.code_maps else self.code
		return struct.pack(self.ts_format, secs, usecs) + \
			struct.pack(self.format, packed_type, packed_code, self.value)

	def unpack(self, s):
		'''Unpack ourselves from the given string, an
			input_event struct in the local byte order.'''
		ts_len = struct.calcsize(self.ts_format)
		secs, usecs = struct.unpack(self.ts_format, s[:ts_len])
		packed_type, packed_code, self.value = struct.unpack(self.format, s[ts_len:])
		self.timestamp = secs + (usecs / 1000000.0)
		self.type = self.type_map[packed_type]
		self.code = self.code_maps[self.type][packed_code] \
			if self.type in self.code_maps else packed_code
		self.scan_code = packed_code

	def read_from(self, stream):
		'Read the next event from the given file-like object'
		self.unpack(stream.read(Event.get_format_size()))


from contextlib import contextmanager
class Control(object):
	_interface = None
	_translate = { ' ': 'SPACE',
		'.': 'DOT',
		',': 'COMMA',
		'\n': 'ENTER',
		'\t': 'TAB',
		';': 'SEMICOLON',
		':': 'COLON',
		'=': 'EQUAL',
		'-': 'MINUS',
		'+': 'PLUS' }

	def __init__(self, path, persistent=False):
		self._interface = open(path, 'wb', 0) if persistent else path

	@contextmanager
	def _if_bind(self):
		if isinstance(self._interface, file): yield self._interface
		else:
			interface = open(self._interface, 'wb', 0)
			ex = None
			try: yield interface
			except Exception as ex: pass
			finally: interface.close()
			if ex: raise ex

	def key(self, *code, **kwz):
		delay = kwz.get('delay', 0)
		with self._if_bind() as interface:
			release = list()
			for code in it.imap(op.methodcaller('upper'), code):
				try: code = self._translate[code]
				except KeyError: pass
				code = 'KEY_%s'%code
				release.append(code)
				self._key_syn( interface,
					Event(type='EV_KEY', code=code, value=1) )
				sleep(delay)
			while release:
				self._key_syn( interface,
					Event( type='EV_KEY', code=release.pop(), value=0) )
				sleep(delay)

	def _key_syn(self, interface, key):
		interface.write(Event(
			type='EV_SYN', code='SYN_REPORT', value=0 ).pack())
		# interface.write(Event(
		# 	type='EV_MSC', code='MSC_SCAN', value=key.scan_code ).pack())
		interface.write(key.pack())

	def write(self, *argz, **kwz):
		if len(argz) == 1: argz = argz[0]
		for key in argz: self.key(key.upper(), **kwz)


if __name__ == "__main__":
	# Open the event device named on the command line, use incoming
	#  events to update a device, and show the state of this device.
	log.cfg(level=log.DEBUG)
	dev = DeviceGroup(sys.argv[1:])
	# event = Event(type='EV_KEY', code='KEY_ENTER', value=1)
	while 1:
		event = dev.next_event()
		if event is not None:
			print repr(event)
			if event.type == "EV_KEY" and event.value == 1:
				if event.code.startswith("KEY"):
					print event.scan_code
				elif event.code.startswith("BTN"):
					print event.code

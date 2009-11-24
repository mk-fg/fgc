from aexec import AExec, Threader, PIPE, Time, Size, End
from dta import chain
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
	'''Managed task creation, which can have callback and
	 is a subject to further management via wait function.
	Any non-absolute cmd paths are subject to extension
	 relative to cfg.paths.bin parameter, if any.
	Special kwz:
		sys - simulates os.system call (but w/ solid argz and extended
		 management), implies block.
		block - blocking execution.
		silent - redirect pipes to /dev/null, close stdin.
		callback - started or scheduled after wait call, see callback function.
		sync - synchronous (native) I/O descriptors. False is MutEx w/ sys and block.'''
	try: block = kwz.pop('block')
	except KeyError: block = False
	try:
		if kwz.pop('silent'): kwz.update(dict(stdin=False, stdout=False, stderr=False))
	except KeyError: void = False
	try:
		block |= kwz.pop('sys')
		kwz.update(dict(stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr))
	except KeyError: pass
	try: cb = kwz.pop('callback')
	except KeyError: cb = None

	if not block: _sem_lock() # callback is mandatory in this case, to release semaphore

	if isinstance(argz[0], (str, unicode)): argz = [argz]
	if not argz[0][0].startswith('/'):
		try:
			from config import cfg
			argz[0][0] = os.path.join(cfg.paths.bin, argz[0][0])
		except (ImportError, AttributeError): pass

	ps = proc(*argz, **kwz)
	if not block: queue.append((ps, cb))
	else:
		if not cb:
			try: return ps.wait()
			except KeyboardInterrupt, ex:
				os.kill(ps.pid, signal.SIGINT)
				ps.wait() # second SIGINT will kill python
		else:
			err = ps.wait()
			callback(cb)
			return err

_ = add # for compatibility reasons


_void = None
def proc(*argz, **kwz):
	global _void
	if isinstance(argz[0], (str, unicode)): argz = [argz]
	if kwz.get('env') is True:
		argz[0] = list(chain('/usr/bin/env', argz[0]))
		del kwz['env']
	for kw in ('stdout', 'stderr'):
		if kwz.get(kw) is False:
			if not _void: _void = open('/dev/null', 'w')
			kwz[kw] = _void
	proc = AExec(*argz, **kwz)
	if kwz.get('stdin') is False and proc.stdin: proc.stdin.close()
	return proc

def pipe(*argz, **kwz):
	nkwz = dict(stdin=PIPE, stdout=PIPE, stderr=PIPE)
	nkwz.update(kwz)
	return proc(*argz, **nkwz)


def wait(n=-1):
	'''Wait for running subprocesses to finish.
	 n can be set to 0 (or None), to wait only for currently running
	 processes, but not their callbacks, if any. If n is lesser than zero
	 itll run till all subprocesses have died.'''
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
	'''Run callback, extracted from passed function.
	Callback will be interpreted as following:
		- (callable, keywords), if second element is dict
		- (callable, arguments), if its some iterable
		- (callable, argument), otherwise
		- callable, if passed spec is not a two-element iterable'''
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


import traceback

def ext_traceback():
	message = buffer('')
	tb = sys.exc_info()[2]
	while True:
		if not tb.tb_next: break
		tb = tb.tb_next
	stack = list()
	frame = tb.tb_frame
	while frame:
		stack.append(frame)
		frame = frame.f_back
	stack.reverse()
	message += traceback.format_exc()
	message += 'Locals by frame, innermost last\n'
	for frame in stack:
		message += '\nFrame %s in %s at line %s\n' \
			% (frame.f_code.co_name, frame.f_code.co_filename, frame.f_lineno)
		for var,val in frame.f_locals.items():
			message += "  %20s = "%var
			try: message += "%s\n"%val
			except:
				try: message += "%r\n"%val
				except: message += "<str/repr failed>\n"
	return message

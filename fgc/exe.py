from fgc.aio import AExec, PIPE, STDOUT, Time, Size, End
from fgc.compat import string_types


_void = None
def proc(*argz, **kwz):
	global _void
	if isinstance(argz[0], string_types):
		argz = [list(argz)]
	else:
		argz = list(argz)
		argz[0] = list(argz[0])
	if kwz.get('env') is True:
		argz[0].insert(0, '/usr/bin/env')
		del kwz['env']
	try:
		if not kwz.pop('silent'): raise KeyError
	except KeyError: pass
	else: kwz['stdout'] = kwz['stderr'] = False
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


import traceback
import sys

def ext_traceback():
	message = ''
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

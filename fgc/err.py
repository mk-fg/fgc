from .compat import string_types
from .enc import enc_default
import sys, traceback

max_val_len = 70

def ext_traceback(to=None, dump_locals=False):
	message = u''
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
	err = traceback.format_exc()
	message += unicode(err)
	if dump_locals:
		message += u'Locals by frame, innermost last\n'
		try: message += unicode(_ext_traceback_locals(stack), enc_default)
		except Exception as err: message += u'<Epic fail: {0!r}>\n'.format(err)
	return message if to is None else to.write(message)

def _ext_traceback_locals(stack):
	message = u''
	for frame in stack:
		message += u'\nFrame {0} in {1} at line {2}\n'\
			.format(frame.f_code.co_name, frame.f_code.co_filename, frame.f_lineno)
		for var,val in frame.f_locals.items():
			message += u'{0:>20} = '.format(var)
			try: val = unicode(val, enc_default)
			except UnicodeError: val = u'<some gibberish>'
			message += u'{0!s}\n'.format(val[:max_val_len])
	return message

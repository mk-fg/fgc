import sys, traceback

max_val_len = 70

def ext_traceback(decode_enc='utf-8'):
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
	try: message += err
	except UnicodeDecodeError: message += err.decode(decode_enc)
	message += u'Locals by frame, innermost last\n'
	try: message += _ext_traceback_locals(stack, decode_enc)
	except Exception as err: message += u'<Epic fail: {0!r}>\n'.format(err)
	return message

def _ext_traceback_locals(stack, decode_enc):
	message = u''
	for frame in stack:
		message += u'\nFrame {0} in {1} at line {2}\n'\
			.format(frame.f_code.co_name, frame.f_code.co_filename, frame.f_lineno)
		for var,val in frame.f_locals.items():
			message += u'{0:>20} = '.format(var)
			# try:
			try: val = unicode(val)
			except (UnicodeDecodeError, UnicodeEncodeError):
				try: val = str(val).decode(decode_enc)
				except (UnicodeDecodeError, UnicodeEncodeError):
					val = u'<some gibberish>'
			# except: val = u''
			message += u'{0!s}\n'.format(val[:max_val_len])
	return message

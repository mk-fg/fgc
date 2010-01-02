import logging, sys
logging._extz = []
logging.currentframe = lambda: sys._getframe(4) # skip traces from this module
ls = logging.getLogger('core')
ls._errz = ls._msgz = 0
ls._errl = logging.WARNING # Which msgz are considered worth reporting on errz() call


class DevNull(logging.Handler):
	def emit(self, record): pass


for val,name in logging._levelNames.iteritems():
	if isinstance(val, int): exec '%s=%s'%(name,val)

def fatal(*argz, **kwz):
	if ls.level <= CRITICAL: ls._msgz += 1
	if ls._errl <= CRITICAL: ls._errz += 1
	try: crash = kwz.pop('crash')
	except KeyError: pass
	else:
		ls.critical(*argz, **kwz)
		sys.exit(crash)
	return ls.critical(*argz, **kwz)
def error(*argz, **kwz):
	if ls.level <= ERROR: ls._msgz += 1
	if ls._errl <= ERROR: ls._errz += 1
	return ls.error(*argz, **kwz)
def warn(*argz, **kwz):
	if ls.level <= WARNING: ls._msgz += 1
	if ls._errl <= WARNING: ls._errz += 1
	return ls.warning(*argz, **kwz)
def info(*argz, **kwz):
	if ls.level <= INFO: ls._msgz += 1
	if ls._errl <= INFO: ls._errz += 1
	return ls.info(*argz, **kwz)
def debug(*argz, **kwz):
	if ls.level <= DEBUG: ls._msgz += 1
	if ls._errl <= DEBUG: ls._errz += 1
	return ls.debug(*argz, **kwz)

errz = lambda: ls._errz
msgz = lambda: ls._msgz
add_handler = ls.addHandler
add_filter = ls.addFilter


def _add_handlers(log, kwz):
	try: key = kwz.pop('stream')
	except KeyError: log.addHandler(DevNull())
	else:
		if not isinstance(key, (list,tuple)): key = (key,)
		for stream in key:
			handler = logging.StreamHandler(stream)
			format = []
			if 'format' in kwz:
				format.append(kwz['format'])
				if 'datefmt' in kwz: format.append(kwz['datefmt'])
			if format: handler.setFormatter(logging.Formatter(*format))
			log.addHandler(handler)


def cfg(*argz, **kwz):
	'''Set core logging stream properties'''
	try: key = kwz.pop('err_threshold')
	except KeyError: pass
	else: ls._errl = key
	kwz_ext = { # default format
		'format': '%(asctime)s %(levelname)s %(module)s.%(funcName)s: %(message)s',
		'datefmt': '(%d.%m.%y %H:%M:%S)'
	}
	try:
		if kwz['format'] is True: kwz.update(kwz_ext) # use default for a given streams as well
	except: kwz_ext.update(kwz)
	_add_handlers(ls, kwz)
	logging.basicConfig(*argz, **kwz_ext)
	try: ls.setLevel(kwz['level'])
	except: pass

def extra(*argz, **kwz):
	'''Add extra logging stream'''
	ext = logging.getLogger('ext_%d'%len(logging._extz))
	logging._extz.append(ext)
	_add_handlers(ext, kwz)
	return ext


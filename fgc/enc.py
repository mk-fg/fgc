import sys
enc_default = sys.getdefaultencoding()
if enc_default in ('ascii', 'ANSI_X3.4-1968'): enc_default = 'utf-8' # ascii is always bad idea


def dec(string, enc=None):
	if isinstance(string, unicode): return string
	else: return unicode(bytes(string), enc or enc_default)


from cStringIO import StringIO as sio

def get(src):
	src_enc = None
	sets = (
		('utf-8', (0xd0,), lambda x: x > max(encs.values()) / 10),
		('koi8-r', xrange(0xc0, 0xdf), 0),
		('cp1251', xrange(0xe0, 0xff), 0) )
	encs = dict([(enc[0], 0) for enc in sets])
	if isinstance(src, str): src = sio(src)
	src.seek(0)
	chr = ord(src.read(1))
	while chr:
		for enc,rng,thresh in sets:
			if chr in rng:
				encs[enc] += 1
				if thresh and isinstance(thresh, int) and encs[enc] > thresh:
					src_enc = enc
					break
			if src_enc: break
			try: chr = ord(src.read(1))
			except TypeError: chr = None
	else:
		for enc,rng,thresh in sets:
			try:
				if thresh(encs[enc]): src_enc = enc
			except TypeError: pass
		if not src_enc: src_enc = sorted(encs, key=lambda x: encs[x], reverse=True)[0]
	return src_enc

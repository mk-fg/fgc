#-*- coding: utf-8 -*-
from __future__ import print_function

import sys, io, types

enc_default = sys.getdefaultencoding()
if enc_default in ('ascii', 'ANSI_X3.4-1968'): enc_default = 'utf-8' # ascii is always bad idea


def dec(string, enc=None):
	if isinstance(string, unicode): return string
	else: return unicode(bytes(string), enc or enc_default)


def get(src):
	src_enc = None
	sets = (
		('utf-8', (0xd0,), lambda x: x > max(encs.values()) / 10),
		('koi8-r', xrange(0xc0, 0xdf), 0),
		('cp1251', xrange(0xe0, 0xff), 0) )
	encs = dict([(enc[0], 0) for enc in sets])
	if isinstance(src, str): src = io.BytesIO(src)
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


def force_bytes(bytes_or_unicode, encoding=None, errors='backslashreplace'):
	encoding = encoding or enc_default
	if isinstance(bytes_or_unicode, bytes): return bytes_or_unicode
	return bytes_or_unicode.encode(encoding, errors)

def force_unicode(bytes_or_unicode, encoding=None, errors='replace'):
	encoding = encoding or enc_default
	if isinstance(bytes_or_unicode, unicode): return bytes_or_unicode
	return bytes_or_unicode.decode(encoding, errors)

def to_bytes(obj, **conv_kws):
	if not isinstance(obj, types.StringTypes): obj = bytes(obj)
	return force_bytes(obj)

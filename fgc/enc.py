from __future__ import print_function
from cStringIO import StringIO
import os


def get(src):
	src_enc = None
	sets = (
		('utf-8', (0xd0,), lambda x: x > max(encs.values()) / 10),
		('koi8-r', xrange(0xc0, 0xdf), 0),
		('cp1251', xrange(0xe0, 0xff), 0)
	)
	encs = dict([(enc[0], 0) for enc in sets])
	if isinstance(src, str): src = StringIO(src)
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


def recode(src, dst_enc, dst=None, src_enc=None, err_thresh=10, onerror=print):
	errz = 0
	if isinstance(src, str): src = StringIO(src)
	dst_buffer = dst or StringIO()
	if not src_enc: src_enc = get(src)
	src.seek(0)
	chr = src.read(1)
	while chr:
		try: chr = chr.decode(src_enc).encode(dst_enc)
		except UnicodeDecodeError as err:
			try:
				schr = src.read(1)
				if schr:
					chr += schr
					chr = chr.decode(src_enc).encode(dst_enc)
				else: break
			except (UnicodeDecodeError,RuntimeError) as err:
				onerror(err)
				errz += 1
				if err_thresh and errz > err_thresh: raise RuntimeError, 'Too many decoding errors'
				src.seek(-1, os.SEEK_CUR)
		dst_buffer.write(chr)
		chr = src.read(1)
	dst_buffer.seek(0)
	return dst or dst_buffer.read()

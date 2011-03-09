import itertools as it, operator as op, functools as ft
from fgc.stracl import from_mode as stracl_from_mode,\
	get as stracl_get, set as stracl_set,\
	ACL_TYPE_ACCESS, ACL_TYPE_DEFAULT
from fgc.sh import Error
import os, types


_mode = lambda x: '::' in x
_eff_drop = lambda x: x.split('\t')[0]
_eff_set = lambda x: '{0}:{1}'.format(
	x.split('\t')[0].rsplit(':', 1)[0], x.rsplit('\t')[-1].rsplit(':', 1)[-1] )
_def_get = lambda x: x.startswith('d:')
_def_set = lambda x: 'd:{0}'.format(x)
_def_strip = op.itemgetter(slice(2, None))
_line_id = lambda x:\
	(x[0] if not x.startswith('d:') else x[:3])\
		if _mode(x) else x.rsplit(':', 1)[0]


def from_mode(mode):
	return canonized(stracl_from_mode(mode))


def get( node, mode_filter=None,
		effective=True, acl_type=None ):
	'Get ACL for a given path, file or fd'
	acl = list()
	effective = _eff_set if effective else _eff_drop
	if mode_filter is None: mode_filter = iter
	else:
		mode_filter = ft.partial(
			it.ifilter if mode_filter else it.ifilterfalse, _mode )
	if not acl_type or acl_type & ACL_TYPE_ACCESS:
		acl = it.chain(acl, it.imap(
			effective, mode_filter(stracl_get(node).splitlines())))
	if (not acl_type or acl_type & ACL_TYPE_DEFAULT) and \
			isinstance(node, types.StringTypes) and os.path.isdir(node):
		acl = it.chain(acl, it.imap(_def_set, it.imap( effective,
			mode_filter(stracl_get(node, ACL_TYPE_DEFAULT).splitlines()) )))
	return list(acl)


_mode_bits = (
	0400, 0200, 0100, # rwx --- ---
	0040, 0020, 0010, # --- rwx ---
	0004, 0002, 0001 )# --- --- rwx

def mode(strspec, base=0):
	for n in xrange(len(_mode_bits)):
		if strspec[n] != '-': base |= _mode_bits[n]
	return base

def get_mode(acl):
	'Get mode from acl, path, file or fd'
	if isinstance(acl, (int, types.StringTypes)):
		acl = get(acl, mode_filter=True, acl_type=ACL_TYPE_ACCESS)
	acl = dict((line[0], line[3:]) for line in it.ifilter(_mode, acl))
	return mode(''.join(acl[x] for x in 'ugo'))


def rebase(acl, node, base=None, discard_old_mode=False):
	'Rebase given ACL lines on top of ones, generated from mode'
	acl = canonized(acl)

	# ACL base
	if not base and not base == 0: # get current base, if unspecified
		base = filter(_mode, get(
			node, mode_filter=True, acl_type=ACL_TYPE_ACCESS ))
	else: # convert given mode to a canonical base-ACL
		if not isinstance(base, (int, long)):
			try: base = mode(base)
			except Error: pass
		base = from_mode(int(base))

	# Access ACL
	ext = it.ifilterfalse(_def_get, acl)
	stracl_set( '\n'.join( update(ext, base)
		if discard_old_mode else update(base, ext) ),
		node, ACL_TYPE_ACCESS )

	# Default ACL
	if isinstance(node, types.StringTypes) and os.path.isdir(node):
		ext = it.imap(_def_strip, it.ifilter(_def_get, acl))
		stracl_set( '\n'.join( update(ext, base)
			if discard_old_mode else update(base, ext) ),
			node, ACL_TYPE_DEFAULT )


def apply(acl, node):
	'''Just set ACL to a given value,
	 which must contain all mode-lines as well'''
	acl = canonized(acl)
	stracl_set('\n'.join(it.ifilterfalse(_def_get, acl)), node)
	if isinstance(node, types.StringTypes) and os.path.isdir(node):
		stracl_set( '\n'.join(it.imap(
				_def_strip, it.ifilter(_def_get, acl) )),
			node, ACL_TYPE_DEFAULT )


def update(base, ext):
	'Rebase one ACL on top of the other'
	res = dict((_line_id(line), line) for line in base)
	res.update((_line_id(line), line) for line in ext)
	return res.values()

def update_from_default(acl):
	'''Update non-default acl lines from default lines,
			possibly overriding acls for the same target.
		Useful to fix mask-crippled acls after chmod.'''
	if not has_defaults(acl): return acl
	return update(acl, (line[2:] for line in acl if line.startswith('d:')))

def canonized(acl):
	'Break down ACL string into a list-form'
	if isinstance(acl, types.StringTypes):
		acl = filter(
			lambda x: x and x[0] != '#',
			acl.replace('\n', ',').split(',') )
	return acl

def has_defaults(acl):
	'Check if ACL has "default" entries'
	for line in acl:
		if _def_get(line): return True
	else: return False

def is_mode(acl):
	'Check if ACL is just a reflection of mode bitmask'
	for line in acl:
		if not _mode(line) or _def_get(line): return False
	else: return True


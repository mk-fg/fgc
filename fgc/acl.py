import itertools as it, operator as op, functools as ft
from fgc.stracl import get as stracl_get, \
	set as stracl_set, ACL_TYPE_ACCESS, ACL_TYPE_DEFAULT
import os, types


_eff_drop = lambda x: x.split('\t')[0]
_mode = lambda x: '::' in x
_def_get = lambda x: x.startswith('d:')
_def_set = lambda x: 'd:{0}'.format(_eff_drop(x))
_def_strip = op.itemgetter(slice(2, None))


def acl_get(node, mode_filter=False, acl_type=None):
	'Get ACL for a given path, file or fd'
	acl = list()
	if mode_filter is not None:
		mode_filter = ft.partial(
			it.ifilter if mode_filter else it.ifilterfalse, _mode )
	if acl_type == ACL_TYPE_ACCESS:
		acl = it.chain(acl, it.imap(
			_eff_drop, mode_filter(
				stracl_get(node).splitlines() )))
	if acl_type != ACL_TYPE_ACCESS and \
			isinstance(node, types.StringTypes) and os.path.isdir(node):
		acl = it.chain(acl, it.imap(_def_set, mode_filter(
			stracl_get(node, ACL_TYPE_DEFAULT).splitlines() )))
	return list(acl)


def acl_rebase(node, acl):
	'Rebase given ACL lines on top of mode-generated ones'
	# Get current base
	base = filter(_mode, acl_get(
		node, mode_filter=True, acl_type=ACL_TYPE_ACCESS ))
	# Access ACL
	access = it.chain(base, it.ifilterfalse(
		_mode, it.ifilterfalse(_def_get, acl) ))
	stracl_set('\n'.join(access), node)
	# Default ACL
	if isinstance(node, types.StringTypes) and os.path.isdir(node):
		stracl_set('\n'.join(it.chain(
			it.ifilterfalse(_mode, it.imap(
				_def_strip, it.ifilter(_def_get, acl) )),
			base )), node, ACL_TYPE_DEFAULT)


def acl_set(node, acl):
	'''Just set ACL to a given lines.
	Given ACL must contain all mode-lines.'''
	stracl_set('\n'.join(it.ifilterfalse(_def_get, acl)), node)
	if isinstance(node, types.StringTypes) and os.path.isdir(node):
		stracl_set( '\n'.join(it.imap(
				_def_strip, it.ifilter(_def_get, acl) )),
			node, ACL_TYPE_DEFAULT )


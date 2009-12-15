import itertools as it, operator as op, functools as ft
from fgc.dta import ProxyObject

import gtk
from Xlib import X, display


_xlib_dpy = None
_xlib_cache = dict()


def _xlib_atom(name):
	global _xlib_dpy, _xlib_win_cache
	try: return _xlib_cache[name]
	except KeyError:
		if not _xlib_dpy: _xlib_dpy = display.Display()
		atom = _xlib_cache[name] = \
			_xlib_dpy.intern_atom(name, only_if_exists=1)
		return atom


class Window(ProxyObject):

	@classmethod
	def get_active(cls, screen=None):
		if screen is None: screen = gtk.gdk.screen_get_default()

		if screen.supports_net_wm_hint('_NET_ACTIVE_WINDOW') \
				and screen.supports_net_wm_hint('_NET_WM_WINDOW_TYPE'):
			win_gdk = screen.get_active_window()
		else: return None

		# Check if 'window' is actually a desktop
		try:
			if win_gdk.get_property('_NET_WM_WINDOW_TYPE')[-1][0] == \
				'_NET_WM_WINDOW_TYPE_DESKTOP': return None
		except TypeError: pass

		win_proxy = cls(win_gdk)
		return win_proxy

	@property
	def _xlib_win(self):
		global _xlib_dpy, _xlib_win_cache
		try: return _xlib_cache[self.xid]
		except KeyError:
			if not _xlib_dpy: _xlib_dpy = display.Display()
			win = _xlib_cache[self.xid] = \
				_xlib_dpy.create_resource_object('window', self.xid)
			return win

	def bounds_chk(self, jitter=None, state=None):
		if state is not None and self.get_state() & state: return True
		xlib_props = self._xlib_win.get_property(
			_xlib_atom('_NET_WM_STATE'), X.AnyPropertyType, 0, 100 )
		if xlib_props and (
				_xlib_atom('_NET_WM_STATE_FULLSCREEN') in xlib_props.value or (
					_xlib_atom('_NET_WM_STATE_MAXIMIZED_HORZ') in xlib_props.value
					and _xlib_atom('_NET_WM_STATE_MAXIMIZED_VERT') in xlib_props.value ) ):
			return True
		if jitter is not None:
			screen = self.get_screen()
			if max(it.imap(abs, it.imap( op.sub, self.get_size(),
				(screen.get_width(), screen.get_height()) ))) <= jitter: return True
		return False

	@property
	def maximized(self):
		return self.bounds_chk( 50,
			gtk.gdk.WINDOW_STATE_MAXIMIZED )

	@property
	def fullscreen(self):
		return self.bounds_chk( 0,
			gtk.gdk.WINDOW_STATE_FULLSCREEN )


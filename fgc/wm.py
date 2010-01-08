import itertools as it, operator as op, functools as ft
from fgc.dta import cached, ProxyObject

import gtk
from Xlib import X, display


@cached
def _xlib_dpy(): return display.Display()

@cached
def _xlib_atom(name):
	return _xlib_dpy().intern_atom(name, only_if_exists=1)

def _xlib_iter():
	def __xlib_iter(win):
		try: leaves = win.query_tree().children
		except AttributeError: pass
		else:
			return it.chain( leaves,
				it.chain.from_iterable(it.imap(__xlib_iter, leaves)) )
	dpy = _xlib_dpy()
	return it.chain.from_iterable(
		__xlib_iter(dpy.screen(scr).root)
		for scr in xrange(dpy.screen_count()) )


def _xlib_filter_pid(pid, xwin):
	prop = xwin.get_property(
		_xlib_atom('_NET_WM_PID'), X.AnyPropertyType, 0, 1 )
	if prop and prop.value[0] == pid: return True
	else: return False



class Window(ProxyObject):


	@classmethod
	def from_xwin(cls, xwin, xwin_iter=None):
		win = cls(gtk.gdk.window_foreign_new(xwin.id))
		if xwin_iter is not None: win._xwin_iter = xwin_iter
		win._xwin = xwin
		return win


	@classmethod
	def by_pid(cls, pid):
		xwin_iter = it.ifilter(ft.partial(
			_xlib_filter_pid, pid ), _xlib_iter())
		try: xwin = xwin_iter.next()
		except StopIteration: return None
		else:
			win = cls.from_xwin(xwin, xwin_iter)
			return win


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


	def __iter__(self):
		'Cycle thru classmethod-matched windows'
		yield self
		while True:
			try: yield self.next()
			except StopIteration: break

	def next(self):
		'Cycle thru classmethod-matched windows'
		return self.__class__.from_xwin(self._xwin_iter.next(), self._xwin_iter)


	_xwin = None
	@property
	def _xlib_win(self):
		if self._xwin: return self._xwin
		else:
			xlib_win = self._xwin = \
				_xlib_dpy().create_resource_object('window', self.xid)
			return xlib_win


	def bounds_chk(self, jitter=None, state=None):
		if state is not None and self.get_state() & state: return True
		xlib_props = self._xlib_win.get_property(
			_xlib_atom('_NET_WM_STATE'), X.AnyPropertyType, 0, 100 )
		if xlib_props and ( # feel teh backhand of human-readable varz! ;)
				_xlib_atom('_NET_WM_STATE_FULLSCREEN') in xlib_props.value
					or ( state & gtk.gdk.WINDOW_STATE_MAXIMIZED
						and not state & gtk.gdk.WINDOW_STATE_FULLSCREEN
						and (_xlib_atom('_NET_WM_STATE_MAXIMIZED_HORZ') in xlib_props.value
							and _xlib_atom('_NET_WM_STATE_MAXIMIZED_VERT') in xlib_props.value) ) ):
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

	@property
	def pid(self):
		xlib_props = self._xlib_win.get_property(
			_xlib_atom('_NET_WM_PID'), X.AnyPropertyType, 0, 100 )
		return xlib_props.value[0]


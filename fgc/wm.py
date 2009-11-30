import itertools as it, operator as op, functools as ft
from fgc.dta import ProxyObject
import gtk


class Window(ProxyObject):

	@classmethod
	def get_active(cls, screen=None):
		if screen is None: screen = gtk.gdk.screen_get_default()

		if screen.supports_net_wm_hint('_NET_ACTIVE_WINDOW') \
				and screen.supports_net_wm_hint('_NET_WM_WINDOW_TYPE'):
			win = screen.get_active_window()
		else: return None

		# Check if 'window' is actually a desktop
		try:
			if win.get_property('_NET_WM_WINDOW_TYPE')[-1][0] == \
				'_NET_WM_WINDOW_TYPE_DESKTOP': return None
		except TypeError: pass

		win_proxy = cls(win)
		return win_proxy


	def bounds_chk(self, jitter=0, state=0):
		screen = self.get_screen()
		if max(it.imap(abs, it.imap( op.sub, self.get_size(),
			(screen.get_width(), screen.get_height()) ))) <= jitter: return True
		return bool(self.get_state() & state)

	@property
	def maximized(self):
		return self.bounds_chk( 50,
			gtk.gdk.WINDOW_STATE_MAXIMIZED )

	@property
	def fullscreen(self):
		return self.bounds_chk( 0,
			gtk.gdk.WINDOW_STATE_FULLSCREEN )


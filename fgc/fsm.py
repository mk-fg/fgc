#-*- coding: utf-8 -*-
from __future__ import print_function

import types


class FSMState(Exception):
	def __init__(self, func): self.func = func
	@property
	def name(self): return self.func.func_name


class FSM(object):

	_fsm_state = None

	def _fsm_state_name(self, state):
		if not isinstance(state, types.StringTypes): state = state.name
		return state

	def _fsm_state_switch(self, state):
		state_name = self._fsm_state_name(state)
		state = getattr(self, state_name)
		self._fsm_state, self.state = state.func(self), state_name


	def __init__(self, state='initial'):
		self._fsm_state_switch(state)
		self.next(StopIteration)

	state = None

	def state_changed(self, old, new): pass # can be overidden

	def next(self, event):
		state0, init = self.state, event is StopIteration
		while True:
			try:
				if init:
					if isinstance(self._fsm_state, types.GeneratorType): next(self._fsm_state)
					self.state_changed(state0, self.state)
				if event is not StopIteration:
					if not isinstance(self._fsm_state, types.GeneratorType): raise StopIteration
					self._fsm_state.send(event)
			except StopIteration:
				raise StopIteration('Already reached final state', self.state)
			except FSMState as transition:
				state0, init, event = self.state, True, StopIteration
				self._fsm_state_switch(transition.name)
			else: return self.state


if __name__ == '__main__':

	class DumDum(FSM):

		def state_changed(self, old, new):
			print('state: {} -> {}'.format(old, new))

		@FSMState
		def initial(self):
			# stuff_on_state_enter()
			incoming_conn = yield
			# stuff_on_state_exit()
			raise self.connected # transition

		@FSMState
		def connected(self):
			# stuff_on_state_enter()
			while True:
				auth_data = yield
				if auth_data != 'error': break
			# stuff_on_state_exit()
			raise self.authenticated # transition

		@FSMState
		def authenticated(self):
			# do_stuff()
			while True:
				done = yield
				if done == 'error': raise self.connected # transition back
				if done is True: break
			# do_more_stuff()
			raise self.finished

		@FSMState
		def finished(self):
			# do_final_stuff()
			return

	thing = DumDum()
	for ev, state in [
			('connection', 'connected'),
			('error', 'connected'),
			('error', 'connected'),
			('auth_data', 'authenticated'),
			('error', 'connected'),
			('auth_data', 'authenticated'),
			(False, 'authenticated'),
			(True, 'finished') ]:
		assert thing.next(ev) == state, [ev, state]

# -*- coding: utf-8 -*-
from __future__ import print_function


from ftplib import FTP, print_line, _GLOBAL_DEFAULT_TIMEOUT, CRLF, Error
import ssl, collections

class FTP_TLS(FTP, object):
	'''A FTP subclass which adds TLS support to FTP as described
	in RFC-4217.

	Connect as usual to port 21 securing control connection before
	authenticating.

	Securing data channel requires user to explicitly ask for it
	by calling prot_p() method.

	Usage example:
	>>> from ftplib import FTP_TLS
	>>> ftps = FTP_TLS('ftp.python.org')
	>>> ftps.login()  # login anonimously previously securing control channel
	'230 Guest login ok, access restrictions apply.'
	>>> ftps.prot_p()  # switch to secure data connection
	'200 Protection level set to P'
	>>> ftps.retrlines('LIST')  # list directory content securely
	total 9
	drwxr-xr-x   8 root	 wheel		1024 Jan  3  1994 .
	drwxr-xr-x   8 root	 wheel		1024 Jan  3  1994 ..
	drwxr-xr-x   2 root	 wheel		1024 Jan  3  1994 bin
	drwxr-xr-x   2 root	 wheel		1024 Jan  3  1994 etc
	d-wxrwxr-x   2 ftp	  wheel		1024 Sep  5 13:43 incoming
	drwxr-xr-x   2 root	 wheel		1024 Nov 17  1993 lib
	drwxr-xr-x   6 1094	 wheel		1024 Sep 13 19:07 pub
	drwxr-xr-x   3 root	 wheel		1024 Jan  3  1994 usr
	-rw-r--r--   1 root	 root		  312 Aug  1  1994 welcome.msg
	'226 Transfer complete.'
	>>> ftps.quit()
	'221 Goodbye.'
	>>>
	'''

	def __init__(self, host='', user='', passwd='', acct='', keyfile=None,
			certfile=None, timeout=_GLOBAL_DEFAULT_TIMEOUT):
		self.keyfile = keyfile
		self.certfile = certfile
		self._prot_p = False
		FTP.__init__(self, host, user, passwd, acct, timeout)

	def login(self, user='', passwd='', acct='', secure=True):
		if secure: self.auth_tls()
		FTP.login(self, user, passwd, acct)

	def auth_tls(self):
		'''Set up secure control connection by using TLS.'''
		resp = self.voidcmd('AUTH TLS')
		self.sock = ssl.wrap_socket(self.sock, self.keyfile, self.certfile, ssl_version=ssl.PROTOCOL_TLSv1)
		self.file = self.sock.makefile(mode='rb')
		return resp

	def prot_p(self):
		'''Set up secure data connection.'''
		# PROT defines whether or not the data channel is to be protected.
		# Though RFC-2228 defines four possible protection levels,
		# RFC-4217 only recommends two, Clear and Private.
		# Clear (PROT C) means that no security is to be used on the
		# data-channel, Private (PROT P) means that the data-channel
		# should be protected by TLS.
		# PBSZ command MUST still be issued, but must have a parameter of
		# '0' to indicate that no buffering is taking place and the data
		# connection should not be encapsulated.
		self.voidcmd('PBSZ 0')
		resp = self.voidcmd('PROT P')
		self._prot_p = True
		return resp

	def prot_c(self):
		'''Set up clear text data channel.'''
		resp = self.voidcmd('PROT C')
		self._prot_p = False
		return resp

	# --- Overridden FTP methods

	def ntransfercmd(self, cmd, rest=None):
		conn, size = FTP.ntransfercmd(self, cmd, rest)
		if self._prot_p:
			conn = ssl.wrap_socket(conn, self.keyfile, self.certfile, ssl_version=ssl.PROTOCOL_TLSv1)
		return conn, size

	def retrbinary(self, cmd, bs=8192, rest=None, callback=None):
		self.voidcmd('TYPE I')
		conn = self.transfercmd(cmd, rest)
		while True:
			data = conn.recv(bs)
			if not data: break
			if callback: callback(data)
		# shutdown ssl layer
		if isinstance(conn, ssl.SSLSocket): conn.unwrap()
		conn.close()
		return self.voidresp()

	def retrlines(self, cmd, callback=None):
		if callback is None: callback = print_line
		resp = self.sendcmd('TYPE A')
		conn = self.transfercmd(cmd)
		fp = conn.makefile('rb')
		while True:
			buff = fp.readline()
			if self.debugging > 2: print('*retr*', repr(buff))
			if not buff: break
			if buff[-2:] == CRLF: buff = buff[:-2]
			elif buff[-1:] == '\n': buff = buff[:-1]
			if callback: callback(buff)
		# shutdown ssl layer
		if isinstance(conn, ssl.SSLSocket): conn.unwrap()
		fp.close()
		conn.close()
		return self.voidresp()

	def storbinary(self, cmd, src, bs=8192, callback=None):
		self.voidcmd('TYPE I')
		conn = self.transfercmd(cmd)
		if isinstance(src, collections.Iterator): src = src.next
		elif isinstance(src, collections.Callable): pass
		else: src = ft.partial(src.read, bs)
		while True:
			try: buff = src()
			except StopIteration: buff = ''
			if not buff: break
			conn.sendall(buff)
			if callback: callback(buff)
		# shutdown ssl layer
		if isinstance(conn, ssl.SSLSocket): conn.unwrap()
		conn.close()
		return self.voidresp()

	def storlines(self, cmd, fp, callback=None):
		self.voidcmd('TYPE A')
		conn = self.transfercmd(cmd)
		while True:
			buff = fp.readline()
			if not buff: break
			if buff[-2:] != CRLF:
				if buff[-1] in CRLF: buff = buff[:-1]
				buff = buff + CRLF
			conn.sendall(buff)
			if callback: callback(buff)
		# shutdown ssl layer
		if isinstance(conn, ssl.SSLSocket): conn.unwrap()
		conn.close()
		return self.voidresp()

	# --- Extensions

	def sever(self):
		try: self.quit()
		except Error as ex:
			try: self.close()
			except: pass


import socket, random, re

class AddressError(Exception): pass

def get_socket_info( host,
		port=0, family=0, socktype=0, protocol=0,
		force_unique_address=None, pick_random=False, log=None ):
	if log is False: log = lambda *a,**k: None
	elif log is None: log = logging.getLogger('fgc.net.get_socket_info')
	log_params = [port, family, socktype, protocol]
	log.debug('Resolving addr: %r (params: %s)', host, log_params)
	host = re.sub(r'^\[|\]$', '', host)
	try:
		addrinfo = socket.getaddrinfo(host, port, family, socktype, protocol)
		if not addrinfo: raise socket.gaierror('No addrinfo for host: {}'.format(host))
	except (socket.gaierror, socket.error) as err:
		raise AddressError( 'Failed to resolve host:'
			' {!r} (params: {}) - {} {}'.format(host, log_params, type(err), err) )

	ai_af, ai_addr = set(), list()
	for family, _, _, hostname, addr in addrinfo:
		ai_af.add(family)
		ai_addr.append((addr[0], family))

	if pick_random: return random.choice(ai_addr)

	if len(ai_af) > 1:
		af_names = dict((v, k) for k,v in vars(socket).viewitems() if k.startswith('AF_'))
		ai_af_names = list(af_names.get(af, str(af)) for af in ai_af)
		if socket.AF_INET not in ai_af:
			log.fatal(
				'Ambiguous socket host specification (matches address famlies: %s),'
					' refusing to pick one at random - specify socket family instead. Addresses: %s',
				', '.join(ai_af_names), ', '.join(ai_addr) )
			raise AddressError
		(log.warn if force_unique_address is None else log.info)\
			( 'Specified host matches more than one address'
				' family (%s), using it as IPv4 (AF_INET)', ai_af_names )
		af = socket.AF_INET
	else: af = list(ai_af)[0]

	for addr, family in ai_addr:
		if family == af: break
	else: raise AddressError
	ai_addr_unique = set(ai_addr)
	if len(ai_addr_unique) > 1:
		if force_unique_address:
			raise AddressError('Address matches more than one host: {}'.format(ai_addr_unique))
		log.warn( 'Specified host matches more than'
			' one address (%s), using first one: %s', ai_addr_unique, addr )

	return af, addr

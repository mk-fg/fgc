from ftplib import FTP, print_line, _GLOBAL_DEFAULT_TIMEOUT, CRLF, Error
import ssl

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

	def retrbinary(self, cmd, callback, blocksize=8192, rest=None):
		self.voidcmd('TYPE I')
		conn = self.transfercmd(cmd, rest)
		while True:
			data = conn.recv(blocksize)
			if not data: break
			callback(data)
		# shutdown ssl layer
		if isinstance(conn, ssl.SSLSocket): conn.unwrap()
		conn.close()
		return self.voidresp()

	def retrlines(self, cmd, callback = None):
		if callback is None: callback = print_line
		resp = self.sendcmd('TYPE A')
		conn = self.transfercmd(cmd)
		fp = conn.makefile('rb')
		while True:
			line = fp.readline()
			if self.debugging > 2: print '*retr*', repr(line)
			if not line: break
			if line[-2:] == CRLF: line = line[:-2]
			elif line[-1:] == '\n': line = line[:-1]
			callback(line)
		# shutdown ssl layer
		if isinstance(conn, ssl.SSLSocket): conn.unwrap()
		fp.close()
		conn.close()
		return self.voidresp()

	def storbinary(self, cmd, fp, blocksize=8192, callback=None):
		self.voidcmd('TYPE I')
		conn = self.transfercmd(cmd)
		while True:
			buf = fp.read(blocksize)
			if not buf: break
			conn.sendall(buf)
			if callback: callback(buf)
		# shutdown ssl layer
		if isinstance(conn, ssl.SSLSocket): conn.unwrap()
		conn.close()
		return self.voidresp()

	def storlines(self, cmd, fp, callback=None):
		self.voidcmd('TYPE A')
		conn = self.transfercmd(cmd)
		while True:
			buf = fp.readline()
			if not buf: break
			if buf[-2:] != CRLF:
				if buf[-1] in CRLF: buf = buf[:-1]
				buf = buf + CRLF
			conn.sendall(buf)
			if callback: callback(buf)
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

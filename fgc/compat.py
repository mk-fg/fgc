from platform import python_version_tuple

if int(python_version_tuple()[0]) < 3:
	## Py2

	from types import StringTypes
	string_types = StringTypes
	buffer = buffer

else:
	## Py3

	from warnings import warn

	string_types = str

	def buffer(buff, bs=None):
		warn('Compat import of buffer pseudotype', DeprecationWarning)
		if not buff: return bytes()
		buff = bytes(buff, 'ascii')
		return buff if bs is None else buff[:bs]

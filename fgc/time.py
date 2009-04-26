from datetime import datetime, timedelta, tzinfo
import re

def reldate(date, now = None):
	'''Returns date in easily-readable format'''
	if isinstance(date, str): date = int(date)
	if isinstance(date, (int, float)): date = datetime.fromtimestamp(date)
	if not now: now = datetime.now()
	diff = abs((date.date() - now.date()).days)
	if diff == 0: return date.strftime('%H:%M')
	elif diff == 1: return date.strftime('%H:%M, yesterday')
	elif diff < 7: return date.strftime('%H:%M, last %a').lower()
	elif diff < 14: return 'week ago'
	elif diff < 50: return '-%s weeks'%(diff/7)
	elif diff < 356: return date.strftime('%d %b')
	else: return date.strftime('%b %Y')


rez = {
	'iso': r"(?P<year>[0-9]{4})(-(?P<month>[0-9]{1,2})(-(?P<day>[0-9]{1,2})"\
		r"((?P<separator>.)(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2})(:(?P<second>[0-9]{2})(\.(?P<fraction>[0-9]+))?)?"\
		r"(?P<timezone>Z|(([-+])([0-9]{2}):([0-9]{2})))?)?)?)?",
	'tz': "(?P<prefix>[+-])(?P<hours>[0-9]{2}).(?P<minutes>[0-9]{2})"
}

def match(v, s):
	try: return rez[v].match(s)
	except AttributeError:
		rez[v] = re.compile(rez[v])
		return rez[v].match(s)

class ParseError(Exception):
	'''Raised when there is a problem parsing a date string'''

ZERO = timedelta(0)
class Utc(tzinfo):
	def utcoffset(self, dt): return ZERO
	def tzname(self, dt): return "UTC"
	def dst(self, dt): return ZERO
UTC = Utc()

class FixedOffset(tzinfo):
	def __init__(self, offset_hours, offset_minutes, name):
		self.__offset = timedelta(hours=offset_hours, minutes=offset_minutes)
		self.__name = name
	def utcoffset(self, dt): return self.__offset
	def tzname(self, dt): return self.__name
	def dst(self, dt): return ZERO
	def __repr__(self): return "<FixedOffset %r>" % self.__name

def parse_tz(tzstring, default_timezone=UTC):
	if tzstring == "Z"or tzstring is None: return default_timezone
	m = match('tz', tzstring)
	prefix, hours, minutes = m.groups()
	hours, minutes = int(hours), int(minutes)
	if prefix == "-":
		hours = -hours
		minutes = -minutes
	return FixedOffset(hours, minutes, tzstring)

def parse_iso(datestring, default_timezone=UTC):
	if not isinstance(datestring, basestring): raise ParseError("Expecting a string %r" % datestring)
	m = match('iso', datestring)
	if not m: raise ParseError("Unable to parse date string %r" % datestring)
	groups = m.groupdict()
	tz = parse_tz(groups["timezone"], default_timezone=default_timezone)
	if groups["fraction"] is None: groups["fraction"] = 0
	else: groups["fraction"] = int(float("0.%s" % groups["fraction"]) * 1e6)
	return datetime(
		int(groups["year"]), int(groups["month"]), int(groups["day"]),
		int(groups["hour"]), int(groups["minute"]), int(groups["second"]),
		int(groups["fraction"]), tz
	)

from datetime import datetime
import time

def reldate(date, now=None):
	'Returns date in easily-readable format'
	if isinstance(date, str): date = int(date)
	if isinstance(date, (int, float)): date = datetime.fromtimestamp(date)
	if isinstance(date, time.struct_time): date = datetime(*date[0:5])
	if now is None: now = datetime.now()
	diff = abs((date.date() - now.date()).days)
	if diff == 0: return date.strftime('%H:%M')
	elif diff == 1: return date.strftime('%H:%M, yesterday')
	elif diff < 7: return date.strftime('%H:%M, last %a').lower()
	elif diff < 14: return 'week ago'
	elif diff < 50: return '-%s weeks'%(diff/7)
	elif diff < 356: return date.strftime('%d %b')
	else: return date.strftime('%b %Y')

def htime(secs=None):
	return time.strftime('%d.%m.%y %H:%M:%S', time.localtime(secs))

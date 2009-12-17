#!/usr/bin/env python

from subprocess import Popen, PIPE
from time import sleep, strftime
import os, sys, hashlib

ver_minor = sum(1 for i in Popen(['/usr/bin/env', 'git', 'rev-list',
	'--since=%s'%strftime('01.%m.%Y'), 'master'], stdout=PIPE).stdout)
scons_hash = hashlib.md5(open('setup.py').read()).hexdigest()\
	if os.path.exists('setup.py') else ''

# Regenerate scons
open('setup.py', 'w').write(
	open('setup.tpl.py').read().format(
		version=strftime('%y.%m.{0}').lstrip('0').format(ver_minor) ) )

# Check if no changes to scons were made and pass the commit
if hashlib.md5(open('setup.py').read()).hexdigest() == scons_hash: sys.exit(0)

# Reindex new files in background
if not os.fork():
	os.setsid()
	while True:
		if os.path.exists('.git/index.lock'): sleep(0.2)
		else: break
	Popen(['/usr/bin/env', 'git', 'add', 'setup.py'], env=dict()).wait()
	sys.exit()

# Break commit sequence
print 'Scons system regenerated, re-initiate commit process manually'
sys.exit(1)

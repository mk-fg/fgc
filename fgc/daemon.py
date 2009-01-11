#!/usr/bin/env python

class Seth(LineReceiver):
	delimiter = "\n"
	def lineReceived(self, line):
		print 'waka waka'

factory = Factory()
factory.protocol = Seth

from twisted.internet import reactor

reactor.listenUNIX('/var/run/fgc.sock', factory)
reactor.run()



import itertools as it, operator as op, functools as ft

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email.header import Header
from email.charset import Charset
from email import Encoders
from hosting import auth
import os, sys, inspect, types

def send( dst, subj=None, body=None, files=[],
		src=None, relay='localhost', headers={}, charset='utf-8', encode_headers=False ):
	if not src:
		src = "Py %s/%s <bugs-wh@%s>"%(
			os.path.basename(inspect.stack()[1][1]), # caller script
			inspect.stack()[1][3].strip('<>'), # caller function
			auth.host(short=False) )
	if isinstance(dst, types.StringTypes): dst = [dst]
	if subj is None: subj = '[%s] Error report'%sys.argv[0]
	if body is None: raise TypeError, 'Message body is not specified'

	msg = MIMEMultipart()
	for k,v in headers.iteritems(): msg[k] = v
	msg['From'] = Header(src, charset) if encode_headers else src
	msg['To'] = Header(COMMASPACE.join(dst), charset) \
		if encode_headers else COMMASPACE.join(dst)
	msg['Date'] = formatdate(localtime=True)
	msg['Subject'] = Header(subj, charset) if encode_headers else subj

	msg.attach( MIMEText(body, _charset=charset) )

	for file in files:
		part = MIMEBase('application', "octet-stream")
		part.set_payload(open(file,"rb").read())
		Encoders.encode_base64(part)
		part.add_header('Content-Disposition', 'attachment; filename="%s"'% os.path.basename(file))
		msg.attach(part)

	smtp = smtplib.SMTP(relay)
	smtp.sendmail(src, dst, msg.as_string() )
	smtp.close()


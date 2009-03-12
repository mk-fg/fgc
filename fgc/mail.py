import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders
import os, inspect

def send(dst, subj, body, files=[], src=None, relay='localhost'):
	if not src:
		src = "Py %s/%s <bugs-wh@%s>"%(
			os.path.basename(inspect.stack()[1][1]), # caller script
			inspect.stack()[1][3].strip('<>'), # caller function
			os.uname()[1]
		)
	if not isinstance(dst, (list,tuple)): dst = [dst]

	msg = MIMEMultipart()
	msg['From'] = src
	msg['To'] = COMMASPACE.join(dst)
	msg['Date'] = formatdate(localtime=True)
	msg['Subject'] = subj

	msg.attach( MIMEText(body) )

	for file in files:
		part = MIMEBase('application', "octet-stream")
		part.set_payload( open(file,"rb").read() )
		Encoders.encode_base64(part)
		part.add_header('Content-Disposition', 'attachment; filename="%s"'% os.path.basename(file))
		msg.attach(part)

	smtp = smtplib.SMTP(relay)
	smtp.sendmail(src, dst, msg.as_string() )
	smtp.close()

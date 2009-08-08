import IPython.ipapi, os


def scite(self, filename, linenum):
	print '--- SciTE (%s)'%filename

	cl = ['scite']
	if linenum: cl.append('-goto:%d'%linenum)
	if filename: cl.append(filename)

	os.system(' '.join(cl))


ip = IPython.ipapi.get()
ip.set_hook('editor', scite)

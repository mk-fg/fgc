#include <Python.h>

#include <sys/capability.h>
#include <errno.h>


static PyObject *
strcaps_get_file(PyObject *self, PyObject *args) { // (int) fd / (str) path / (file) file
	PyObject *file;
	if (!PyArg_ParseTuple(args, "O", &file)) return NULL;
	cap_t caps;
	if (PyString_Check(file)) caps = cap_get_file(PyString_AsString(file));
	else if (PyFile_Check(file)) caps = cap_get_fd(PyObject_AsFileDescriptor(file));
	else if (PyInt_Check(file)) caps = cap_get_fd(PyInt_AsLong(file));
	else {
		PyErr_SetString( PyExc_TypeError,
			"Expecting file object, descriptor int or path string" );
		return NULL; }
	int strcaps_len; char *strcaps;
	if (caps == NULL) {
		if (errno == ENODATA) { strcaps = "\0"; strcaps_len = 0; }
		else {
			PyErr_SetString(PyExc_OSError, strerror(errno));
			return NULL; } }
	else strcaps = cap_to_text(caps, &strcaps_len);
	return Py_BuildValue("s#", strcaps, strcaps_len); }; // (str) caps

static PyObject *
strcaps_get_process(PyObject *self, PyObject *args) { // (int) pid or None
	int pid = 0;
	if (!PyArg_ParseTuple(args, "|i", &pid)) return NULL;
	cap_t caps;
	if (!pid) caps = cap_get_proc();
	else caps = cap_get_pid(pid);
	int strcaps_len; char *strcaps;
	if (caps == NULL) {
		if (errno == ENODATA) { strcaps = "\0"; strcaps_len = 0; }
		else {
			PyErr_SetString(PyExc_OSError, strerror(errno));
			return NULL; } }
	else strcaps = cap_to_text(caps, &strcaps_len);
	return Py_BuildValue("s#", strcaps, strcaps_len); }; // (str) caps


static PyObject *
strcaps_set_file(PyObject *self, PyObject *args) { // (str) caps, (int) fd / (str) path / (file) file
	char *strcaps; PyObject *file;
	if (!PyArg_ParseTuple(args, "sO", &strcaps, &file)) return NULL;
	cap_t caps;
	if ((caps = cap_from_text(strcaps)) == NULL) {
		PyErr_SetString(PyExc_ValueError, "Invalid capability specification");
		return NULL; }
	int err;
	if (PyString_Check(file)) err = cap_set_file(PyString_AsString(file), caps);
	else if (PyFile_Check(file)) err = cap_set_fd(PyObject_AsFileDescriptor(file), caps);
	else if (PyInt_Check(file)) err = cap_set_fd(PyInt_AsLong(file), caps);
	else {
		PyErr_SetString( PyExc_TypeError,
			"Expecting file object, descriptor int or path string" );
		return NULL; }
	if (err) {
		PyErr_SetString(PyExc_OSError, strerror(errno));
		return NULL; }
	Py_RETURN_NONE; };

static PyObject *
strcaps_set_process(PyObject *self, PyObject *args) { // (str) caps, (int) pid or None
	char *strcaps; int pid = 0;
	if (!PyArg_ParseTuple(args, "s|i", &strcaps, &pid)) return NULL;
	cap_t caps;
	if ((caps = cap_from_text(strcaps)) == NULL) {
		PyErr_SetString(PyExc_ValueError, "Invalid capability specification");
		return NULL; }
	int err;
	if (!pid) err = cap_set_proc(caps);
	else err = capsetp(pid, caps);
	if (err) {
		PyErr_SetString(PyExc_OSError, strerror(errno));
		return NULL; }
	Py_RETURN_NONE; };



static PyMethodDef strcaps_methods[] = {
	{"get_file", strcaps_get_file, METH_VARARGS,
		"Get capabilities string from path, file or descriptor.\n"},
	{"get_process", strcaps_get_process, METH_VARARGS,
		"Get capabilities string from pid or current thread, if pid is omitted.\n"},
	{"set_file", strcaps_set_file, METH_VARARGS,
		"Set capabilities from string to a path, file or descriptor.\n"},
	{"set_process", strcaps_set_process, METH_VARARGS,
		"Set capabilities from string for a pid or current thread, if pid is omitted,"
		" setting caps for an arbitrary pid is deprecated and might be unsupported.\n"},
	{NULL, NULL, 0, NULL} };

PyDoc_STRVAR( strcaps__doc__,
	"String-based POSIX capabilities manipulation interface." );


PyMODINIT_FUNC
initstrcaps(void) {
	PyObject *module;
	module = Py_InitModule3("strcaps", strcaps_methods, strcaps__doc__); };


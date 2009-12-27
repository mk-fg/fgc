#include <Python.h>

#include <sys/capability.h>
#include <errno.h>


static PyObject *
strcaps_get(PyObject *self, PyObject *args) { // (int) fd / (str) path / (file) file
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
strcaps_set(PyObject *self, PyObject *args) { //  (int) fd / (str) path / (file) file, (str) caps
	PyObject *file; char *strcaps;
	if (!PyArg_ParseTuple(args, "Os", &file, &strcaps)) return NULL;
	cap_t caps;
	if ((caps = cap_from_text(strcaps)) == NULL) {
		PyErr_SetString(PyExc_ValueError, "Invalid capabilities specification");
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



static PyMethodDef strcaps_methods[] = {
	{"get", strcaps_get, METH_VARARGS,
		"Get capabilities string from path, file or descriptor.\n"},
	{"set", strcaps_set, METH_VARARGS,
		"Set capabilities from string to a path, file or descriptor.\n"},
	{NULL, NULL, 0, NULL} };

PyDoc_STRVAR( strcaps__doc__,
	"String-based POSIX capabilities manipulation interface." );


PyMODINIT_FUNC
initstrcaps(void) {
	PyObject *module;
	module = Py_InitModule3("strcaps", strcaps_methods, strcaps__doc__); };


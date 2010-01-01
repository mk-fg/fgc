#include <Python.h>

#include <sys/types.h>
#include <acl/libacl.h>
#include <sys/stat.h>
#include <errno.h>

#define PyFlag(m, c) PyModule_AddIntConstant(m, #c, c)


static PyObject *
stracl_get(PyObject *self, PyObject *args) { // (int) fd / (str) path / (file) file, (int) acl_type
	PyObject *file; int acl_type = ACL_TYPE_ACCESS;
	if (!PyArg_ParseTuple(args, "O|i", &file, &acl_type)) return NULL;
	acl_t acl;
	if (PyString_Check(file)) acl = acl_get_file(PyString_AsString(file), acl_type);
	else if (PyFile_Check(file)) acl = acl_get_fd(PyObject_AsFileDescriptor(file));
	else if (PyInt_Check(file)) acl = acl_get_fd(PyInt_AsLong(file));
	else {
		PyErr_SetString( PyExc_TypeError,
			"Expecting file object, descriptor int or path string" );
		return NULL; }
	char *stracl;
	if (acl == NULL) {
		if (errno == ENODATA) { stracl = "\0"; }
		else {
			PyErr_SetString(PyExc_OSError, strerror(errno));
			return NULL; } }
	else stracl = acl_to_any_text(acl, NULL, '\n', TEXT_ABBREVIATE | TEXT_ALL_EFFECTIVE);
	acl_free(acl);
	return Py_BuildValue("s", stracl); }; // (str) acl


static PyObject *
stracl_get_mode(PyObject *self, PyObject *args) { // (int) fd / (str) path / (file) file
	PyObject *file;
	if (!PyArg_ParseTuple(args, "O", &file)) return NULL;
	struct stat stat_struct; int stat_result;
	if (PyString_Check(file))
		stat_result = stat(PyString_AsString(file), &stat_struct);
	else if (PyFile_Check(file))
		stat_result = fstat(PyObject_AsFileDescriptor(file), &stat_struct);
	else if (PyInt_Check(file))
		stat_result = fstat(PyInt_AsLong(file), &stat_struct);
	else {
		PyErr_SetString( PyExc_TypeError,
			"Expecting file object, descriptor int or path string" );
		return NULL; }
	if (stat_result) {
		PyErr_SetString(PyExc_OSError, strerror(errno));
		return NULL; }
	else {
		char *stracl = acl_to_any_text(
			acl_from_mode(stat_struct.st_mode),
			NULL, '\n', TEXT_ABBREVIATE | TEXT_ALL_EFFECTIVE);
		return Py_BuildValue("s", stracl); } }; // (str) acl


static PyObject *
stracl_set(PyObject *self, PyObject *args) { // (str) acl, (int) fd / (str) path / (file) file, (int) acl_type
	char *stracl; PyObject *file; int acl_type = ACL_TYPE_ACCESS;
	if (!PyArg_ParseTuple(args, "sO|i", &stracl, &file, &acl_type)) return NULL;
	acl_t acl;
	if ((acl = acl_from_text(stracl)) == NULL || acl_calc_mask(&acl)) {
		PyErr_SetString(PyExc_ValueError, "Invalid ACL specification");
		return NULL; }
	int err;
	if (PyString_Check(file)) err = acl_set_file(PyString_AsString(file), acl_type, acl);
	else if (PyFile_Check(file)) err = acl_set_fd(PyObject_AsFileDescriptor(file), acl);
	else if (PyInt_Check(file)) err = acl_set_fd(PyInt_AsLong(file), acl);
	else {
		PyErr_SetString( PyExc_TypeError,
			"Expecting file object, descriptor int or path string" );
		return NULL; }
	if (err) {
		PyErr_SetString(PyExc_OSError, strerror(errno));
		return NULL; }
	acl_free(acl);
	Py_RETURN_NONE; };



static PyMethodDef stracl_methods[] = {
	{"get", stracl_get, METH_VARARGS,
		"Get ACL string from path, file or descriptor.\n"},
	{"get_mode", stracl_get_mode, METH_VARARGS,
		"Get mode-only ACL string from mode of path, file or descriptor.\n"},
	{"set", stracl_set, METH_VARARGS,
		"Set ACL from string to a path, file or descriptor.\n"},
	{NULL, NULL, 0, NULL} };

PyDoc_STRVAR( stracl__doc__,
	"String-based POSIX ACL manipulation interface." );


PyMODINIT_FUNC
initstracl(void) {
	PyObject *module;
	module = Py_InitModule3("stracl", stracl_methods, stracl__doc__);

	PyFlag(module, ACL_TYPE_ACCESS);
	PyFlag(module, ACL_TYPE_DEFAULT); };


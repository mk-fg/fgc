#include <Python.h>

#include <sys/time.h>
#include <stdlib.h>

#include <sys/types.h>
#include <dirent.h>


static PyObject *
posix_error_with_allocated_filename(char* name) {
	PyObject *rc = PyErr_SetFromErrnoWithFilename(PyExc_OSError, name);
	PyMem_Free(name);
	return rc;
}


static int
extract_time(PyObject *ts, long *sec, long *usec) {
	long intval;
	if (PyFloat_Check(ts)) {
		double tval = PyFloat_AsDouble(ts);
		PyObject *intobj = Py_TYPE(ts)->tp_as_number->nb_int(ts);
		if (!intobj) return -1;
		intval = PyInt_AsLong(intobj);
		Py_DECREF(intobj);
		if (intval == -1 && PyErr_Occurred()) return -1;
		*sec = intval;
		*usec = (long)((tval - intval) * 1e6); // can't exceed 1000000
		if (*usec < 0) *usec = 0; } // if rounding gave us a negative number, truncate
	else {
		intval = PyInt_AsLong(ts);
		if (intval == -1 && PyErr_Occurred()) return -1;
		*sec = intval;
		*usec = 0; }
	return 0;
}


static PyObject *
oe_lutimes(PyObject *self, PyObject *args) { // (str) filename, (tuple) (atime, mtime)
	char *path; PyObject *ftimes;
	if (!PyArg_ParseTuple( args, "etO:utime",
		Py_FileSystemDefaultEncoding, &path, &ftimes )) return NULL;

	struct timeval tv[2];

	if (PyTuple_Check(ftimes) && PyTuple_Size(ftimes) == 2) {
		int i;
		for (i=0; i<2; i++) {
			if ( extract_time(PyTuple_GET_ITEM(ftimes, i),
					&tv[i].tv_sec, &tv[i].tv_usec) == -1 ) {
				PyMem_Free(path);
				return NULL; } }

		Py_BEGIN_ALLOW_THREADS
		i = lutimes(path, tv);
		Py_END_ALLOW_THREADS

		if (i < 0) return posix_error_with_allocated_filename(path); }
	else {
		PyErr_SetString(PyExc_TypeError,
			"lutimes() arg 2 must be a tuple (atime, mtime)");
		PyMem_Free(path);
		return NULL; }

	Py_RETURN_NONE; }



typedef struct {
	PyObject_HEAD
	DIR *dir;
} Gen_DirListing;

static void Gen_DirListing_dealloc(Gen_DirListing *self) {
	if (self->dir != NULL) {
		Py_BEGIN_ALLOW_THREADS
		closedir(self->dir);
		Py_END_ALLOW_THREADS }

	Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *Gen_DirListing_iter(PyObject *self, PyObject *args) {
	Py_INCREF(self);
	return self; }

static PyObject *Gen_DirListing_next(PyObject *self, PyObject *args) {
	Gen_DirListing *gen = (Gen_DirListing *)self;
	struct dirent *entry;

	for (;;) {
		errno = 0;
		Py_BEGIN_ALLOW_THREADS
		entry = readdir(gen->dir);
		Py_END_ALLOW_THREADS

		if (entry == NULL) {
			if (errno == 0) PyErr_SetNone(PyExc_StopIteration);
			else PyErr_SetFromErrno(PyExc_OSError);
			break; }

		if (entry->d_name[0] == '.' && ( strlen(entry->d_name) == 1 ||
			(entry->d_name[1] == '.' && strlen(entry->d_name) == 2) )) continue;

		PyObject *py_entry_bytes = PyString_FromStringAndSize(
			entry->d_name, strlen(entry->d_name) );
		if (py_entry_bytes == NULL) return NULL;

		PyObject *py_entry_uc = PyUnicode_FromEncodedObject(
			py_entry_bytes, Py_FileSystemDefaultEncoding, "strict");
		if (py_entry_uc == NULL) { // fallback to byte string
			py_entry_uc = py_entry_bytes;
			PyErr_Clear(); }
		else Py_DECREF(py_entry_bytes);

		return py_entry_uc;
	}

	return NULL;
}

PyTypeObject Gen_DirListingType = {
	PyObject_HEAD_INIT(NULL)
	0, "os_ext._DirListingGenerator", sizeof(Gen_DirListing), 0,
	(destructor)Gen_DirListing_dealloc, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_ITER,
	0, 0, 0, 0, 0, (getiterfunc)Gen_DirListing_iter, (iternextfunc)Gen_DirListing_next };

static PyObject *
oe_listdir(PyObject *self, PyObject *args) { // (str) dirname
	char *path;
	if (!PyArg_ParseTuple( args, "et:path",
		Py_FileSystemDefaultEncoding, &path )) return NULL;

	DIR *dir;
	Py_BEGIN_ALLOW_THREADS
	dir = opendir(path);
	Py_END_ALLOW_THREADS

	if (dir == NULL) return posix_error_with_allocated_filename(path);

	Gen_DirListing *gen;
	if (!(gen = PyObject_New(Gen_DirListing, &Gen_DirListingType))) goto fail;
	if (!PyObject_Init((PyObject *)gen, &Gen_DirListingType)) {
		Py_DECREF(gen);
		goto fail; }

	gen->dir = dir;

	return (PyObject *)gen;

fail:
	Py_BEGIN_ALLOW_THREADS
	closedir(dir);
	Py_END_ALLOW_THREADS

	PyMem_Free(path);
	return NULL; }



static PyMethodDef oe_methods[] = {
	{"lutimes", oe_lutimes, METH_VARARGS,
		"Change atime/mtime of a given inode (w/o dereferencing symlinks).\n"
		"Arguments are path and (atime, mtime) tuple, same as for os.utimes."},
	{"listdir", oe_listdir, METH_VARARGS,
		"List directory contents in iterative fashion. Returns generator object."},
	{NULL, NULL, 0, NULL} };

PyDoc_STRVAR( oe__doc__,
	"Less-conventional OS/libc interfaces" );


PyMODINIT_FUNC
initos_ext(void) {
	PyObject *module;

  if (PyType_Ready(&Gen_DirListingType) < 0) return;

	module = Py_InitModule3("os_ext", oe_methods, oe__doc__);

	Py_INCREF(&Gen_DirListingType);
	PyModule_AddObject(module, "_DirListing", (PyObject *)&Gen_DirListingType); };

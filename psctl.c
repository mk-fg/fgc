#include <Python.h>

#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/user.h>

#include <sys/prctl.h>
#include <linux/securebits.h>

#define PyFlag(m, c) PyModule_AddIntConstant(m, #c, pow(2, c))


static PyObject *
psctl_securebits_set(PyObject *self, PyObject *args) { // (int) bitmask
	int bitmask;
	if (!PyArg_ParseTuple(args, "i", &bitmask)) return NULL;
	prctl(PR_SET_SECUREBITS, bitmask, 0, 0, 0);
	Py_INCREF(Py_None);
	return Py_None; };

static PyObject *
psctl_securebits_get(PyObject *self, PyObject *args) { // no args
	return Py_BuildValue("i", prctl(PR_GET_SECUREBITS, 0, 0, 0, 0)); };


static PyObject *
psctl_name_set(PyObject *self, PyObject *args) { // (str) name, (bool) update_cmdline
	char *name; PyObject *update_cmdline = Py_True;
	if (!PyArg_ParseTuple(args, "s|O", &name, &update_cmdline)) return NULL;

	// Update thread name
	prctl(PR_SET_NAME, name, 0, 0, 0);

	// Update cmdline
	// Implementation is copy-pasted from setproctitle.c in util-linux-ng
	// Name here can be up to 2k bytes, but prctl will only return first 16.
	//	Rest of it is accessible via /proc/X/cmdline, which is also used by procps.
	if (PyObject_IsTrue(update_cmdline)) {
		int argc; char **argv;
		Py_GetArgcArgv(&argc, &argv);

		extern char** environ; char **envp = environ;
		static char** argv0; static int argv_lth;

		int i;
		for (i = 0; envp[i] != NULL; i++) continue;
		environ = (char **) malloc(sizeof(char *) * (i + 1));
		if (environ) {
			for (i = 0; envp[i] != NULL; i++)
				if ((environ[i] = strdup(envp[i])) == NULL) { i = -1; break; }
			if (i != -1) environ[i] = NULL; }

		argv0 = argv;
		if (i > 0) argv_lth = envp[i-1] + strlen(envp[i-1]) - argv0[0];
		else argv_lth = argv0[argc-1] + strlen(argv0[argc-1]) - argv0[0];

		if (argv0) {
			i = strlen(name);
			if (i > argv_lth - 2) {
				i = argv_lth - 2;
				name[i] = '\0'; }
			memset(argv0[0], '\0', argv_lth);
			(void) strcpy(argv0[0], name);
			argv0[1] = NULL; } }

	Py_INCREF(Py_None);
	return Py_None; };

static PyObject *
psctl_name_get(PyObject *self, PyObject *args) { // (bool) from_cmdline
	PyObject *from_cmdline = Py_True;
	if (!PyArg_ParseTuple(args, "|O", &from_cmdline)) return NULL;

	char name[PAGE_SIZE];
	if (PyObject_Not(from_cmdline)) prctl(PR_GET_NAME, &name, 0, 0, 0); // returns at most 16 bytes ;(
	else {
		char cmdline_path[PATH_MAX];
		unsigned int pid = getpid();
		sprintf(cmdline_path, "/proc/%d/cmdline", pid);
		FILE *cmdline_file =  fopen(cmdline_path, "r");
		if (!fgets(name, sizeof(name), cmdline_file)) return NULL;
		fclose(cmdline_file); }

	return Py_BuildValue("s", name); };



static PyMethodDef psctl_methods[] = {
	{"name_set", psctl_name_set, METH_VARARGS,
		"Update process name to a given string.\n"
		"Also rewrites cmdline, which is a quite hacky,"
		" and can be disabled by second argument."},
	{"name_get", psctl_name_get, METH_VARARGS,
		"Get current process name.\n"
		"Reads it from /proc//cmdline by default,"
		" since prctl returns at most 16 bytes.\n"
		"Can be disabled by argument."},
	{"securebits_set", psctl_securebits_set, METH_VARARGS,
		"Set secure bits of the current process to a given value."},
	{"securebits_get", psctl_securebits_get, METH_NOARGS,
		"Get secure bits of the current process."},
	{NULL, NULL, 0, NULL} };

PyDoc_STRVAR( psctl__doc__,
	"Process attributes manipulation interface" );


PyMODINIT_FUNC
initpsctl(void) {
	PyObject *module;
	module = Py_InitModule3("psctl", psctl_methods, psctl__doc__);

	PyFlag(module, SECURE_NOROOT);
	PyFlag(module, SECURE_NOROOT_LOCKED);
	PyFlag(module, SECURE_KEEP_CAPS);
	PyFlag(module, SECURE_KEEP_CAPS_LOCKED);
	PyFlag(module, SECURE_NO_SETUID_FIXUP);
	PyFlag(module, SECURE_NO_SETUID_FIXUP_LOCKED); };


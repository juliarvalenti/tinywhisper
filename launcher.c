#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>

/* Resolve PYTHON_PREFIX at compile time via -DPYTHON_PREFIX="..." */
#ifndef PYTHON_PREFIX
#error "Define PYTHON_PREFIX at compile time"
#endif

int main(int argc, char *argv[]) {
    /* Ensure stdout/stderr are valid fds (Finder launches without a tty) */
    if (fcntl(STDOUT_FILENO, F_GETFD) == -1) {
        int devnull = open("/dev/null", O_WRONLY);
        if (devnull >= 0) { dup2(devnull, STDOUT_FILENO); close(devnull); }
    }
    if (fcntl(STDERR_FILENO, F_GETFD) == -1) {
        int devnull = open("/dev/null", O_WRONLY);
        if (devnull >= 0) { dup2(devnull, STDERR_FILENO); close(devnull); }
    }

    /* Ensure Python uses UTF-8 (Finder launches have no locale set) */
    setenv("PYTHONIOENCODING", "utf-8", 0);
    setenv("LC_ALL", "en_US.UTF-8", 0);

    /* Set PYTHONHOME so embedded Python finds stdlib + site-packages */
    setenv("PYTHONHOME", PYTHON_PREFIX, 1);

    Py_Initialize();
    PyRun_SimpleString(
        "import sys; sys.argv = ['tinywhisper']\n"
        "from tinywhisper.main import main; main()\n"
    );
    if (Py_FinalizeEx() < 0) {
        return 1;
    }
    return 0;
}

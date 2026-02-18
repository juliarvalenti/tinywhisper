#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <mach-o/dyld.h>
#include <limits.h>

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

    /* Set PYTHONHOME so embedded Python finds stdlib */
    setenv("PYTHONHOME", PYTHON_PREFIX, 1);

    Py_Initialize();

    /*
     * Resolve bundled site-packages relative to the binary:
     *   <binary>/../Resources/site-packages
     * This avoids baking an absolute path that may live under ~/Documents/
     * (which would trigger a macOS TCC prompt).
     */
    {
        char exe_path[PATH_MAX];
        uint32_t exe_size = sizeof(exe_path);
        if (_NSGetExecutablePath(exe_path, &exe_size) == 0) {
            /* Strip the binary filename to get the MacOS/ directory */
            char *last_slash = strrchr(exe_path, '/');
            if (last_slash) *last_slash = '\0';
            /* Append /../Resources/site-packages */
            char rel_path[PATH_MAX];
            snprintf(rel_path, sizeof(rel_path),
                     "%s/../Resources/site-packages", exe_path);
            char resolved[PATH_MAX];
            if (realpath(rel_path, resolved)) {
                char insert_cmd[PATH_MAX + 64];
                snprintf(insert_cmd, sizeof(insert_cmd),
                         "import sys; sys.path.insert(0, '%s')", resolved);
                PyRun_SimpleString(insert_cmd);
            }
        }
    }

    PyRun_SimpleString(
        "import sys; sys.argv = ['tinywhisper']\n"
        "from tinywhisper.main import main; main()\n"
    );
    if (Py_FinalizeEx() < 0) {
        return 1;
    }
    return 0;
}

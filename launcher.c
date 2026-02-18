#include <Python.h>

int main(int argc, char *argv[]) {
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

#include <stdio.h>
#include <unistd.h>

FILE *orig_stdin = NULL;
FILE *orig_stdout = NULL;
//FILE *orig_stderr = NULL;

char* initialize();
void add_number(int num);
int get_number();
char* finalize();

int main() {
    // save original descriptors
    int stdin_copy = dup(0);
    int stdout_copy = dup(1);
    //int stderr_copy = dup(2);

    // override original descriptors
    freopen("/dev/null", "r", stdin);
    freopen("/dev/null", "w", stdout);
    freopen("/dev/null", "w", stderr);

    // open original streams
    orig_stdin = fdopen(stdin_copy, "r");
    orig_stdout = fdopen(stdout_copy, "w");
    //orig_stderr = fdopen(stderr_copy, "w");

    fprintf(orig_stdout, "%s\n", initialize());
    fflush(orig_stdout);

    // read commands until we receive exit command
    int num = 0;
    fscanf(orig_stdin, "%d", &num);

    while (num) {
        add_number(num);

        fprintf(orig_stdout, "k\n");
        fflush(orig_stdout);
        fscanf(orig_stdin, "%d", &num);
    }

    fprintf(orig_stdout, "%d\n", get_number());
    fprintf(orig_stdout, "%s\n", finalize());
    fflush(orig_stdout);

    return 0;
}

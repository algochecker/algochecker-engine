#include <stdio.h>
#include <stdlib.h>

int number = 0;
char* hello = "hello";
char* bye = "bye";

char* initialize() {
    return hello;
}

void add_number(int num) {
    number += num;
}

int get_number() {
    while(1);
    return number;
}

char* finalize() {
    return bye;
}

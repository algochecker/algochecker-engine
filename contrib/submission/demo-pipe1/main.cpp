#include <iostream>
#include <random>

using namespace std;

int main()
{
    int status;

    do {
        cout << rand() % 1000001 << endl;
        cin >> status;
    } while (status);

    return 0;
}

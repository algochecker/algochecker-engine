#include <iostream>
#include <unistd.h>

using namespace std;

int main() {
    int x;
    int y;

    cin >> x;
    cin >> y;

    if (x == 17) {
        while (1);
    }

    if (x == 33) {
        sleep(1);
    }

    cout << x+y << endl;

    return 0;
}

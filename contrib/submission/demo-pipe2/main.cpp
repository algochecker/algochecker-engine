#include <iostream>

using namespace std;

int main()
{
    int low_bound = 0;
    int high_bound = 1000000;
    int guess = (high_bound + low_bound) / 2;
    int status;

    do {
        cout << guess << endl;
        cin >> status;

        if (status == 1) {
            // guess > actual_number
            high_bound = guess;
        } else if (status == -1) {
            // guess < actual_number
            low_bound = guess;
        }

        guess = (high_bound + low_bound) / 2;
    } while (status != 0);

    return 0;
}

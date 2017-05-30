#include <iostream>
#include <random>
#include <algorithm>

using namespace std;

int main()
{
    int N;
    cin >> N;

    std::vector<int> numbers;

    for (int i = 0; i < N; i++) {
        int temp;
        cin >> temp;
        numbers.push_back(temp);
    }

    std::random_shuffle(numbers.begin(), numbers.end());

    for (std::vector<int>::iterator it=numbers.begin(); it != numbers.end(); ++it) {
        cout << *it << endl;
    }

    return 0;
}

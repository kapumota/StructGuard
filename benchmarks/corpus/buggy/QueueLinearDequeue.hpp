#pragma once

#include <stdexcept>

class QueueLinearDequeue {
public:
    QueueLinearDequeue() : n(0) {}

    void enqueue(int value) {
        if (n >= 16) {
            throw std::out_of_range("capacidad agotada");
        }
        data[n] = value;
        n += 1;
    }

    int dequeue() {
        if (n <= 0) {
            throw std::out_of_range("cola vacía");
        }
        int value = data[0];
        for (int i = 1; i < n; ++i) {
            data[i - 1] = data[i];
        }
        n -= 1;
        return value;
    }

private:
    int data[16];
    int n;
};

#pragma once

class VectorAppendNoSizeUpdate {
public:
    VectorAppendNoSizeUpdate() : n(0) {}

    void append(int value) {
        data[n] = value;
    }

private:
    int data[16];
    int n;
};

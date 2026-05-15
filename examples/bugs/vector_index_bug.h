#pragma once

class VectorIndexBug {
private:
    int data_[4];
    int size_;
    int capacity_;
public:
    // invariant: size_ >= 0
    // invariant: size_ <= capacity_
    VectorIndexBug() : size_(0), capacity_(4) {}

    // requires: size_ < capacity_
    // ensures: size_ == old(size_) + 1
    void push_back(int value) {
        data_[size_] = value;
        size_++;
    }

    int operator[](int index) const {
        return data_[index];
    }
};

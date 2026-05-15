#pragma once

class DynamicArray {
private:
    int size_;
    int capacity_;

public:
    // invariant: size_ >= 0
    // invariant: capacity_ >= 1
    // invariant: size_ <= capacity_

    // ensures: size_ == 0
    // ensures: capacity_ == 1
    DynamicArray() {
        size_ = 0;
        capacity_ = 1;
    }

    // requires: size_ < capacity_
    // ensures: size_ == old(size_) + 1
    void push_back(int x) {
        size_ = size_ + 1;
    }
};

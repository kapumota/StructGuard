#pragma once

template <typename T>
class RealisticVector {
private:
    T data_[32];
    int size_;
    int capacity_;
public:
    // invariant: size_ >= 0
    // invariant: capacity_ >= 0
    // invariant: size_ <= capacity_
    RealisticVector() : size_(0), capacity_(32) {}

    // ensures: result == size_
    int size() const { return size_; }

    // requires: size_ < capacity_
    // ensures: size_ == old(size_) + 1
    void push_back(const T& value) {
        if (size_ < capacity_) {
            data_[size_] = value;
            size_++;
        }
    }

    // requires: index >= 0
    // requires: index < size_
    T operator[](int index) const {
        return data_[index];
    }
};

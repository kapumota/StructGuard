#pragma once

template <typename T>
class RealisticStack {
private:
    T data_[16];
    int size_;
    int capacity_;
public:
    // invariant: size_ >= 0
    // invariant: size_ <= capacity_
    RealisticStack() : size_(0), capacity_(16) {}

    // ensures: result == (size_ == 0)
    bool empty() const {
        if (size_ == 0) {
            return true;
        }
        return false;
    }

    // requires: size_ < capacity_
    // ensures: size_ == old(size_) + 1
    void push(const T& value) {
        if (size_ < capacity_) {
            data_[size_] = value;
            size_++;
        }
    }

    // requires: size_ > 0
    // ensures: size_ == old(size_) - 1
    void pop() {
        if (size_ > 0) {
            size_--;
        }
    }

    // requires: size_ > 0
    T top() const {
        return data_[size_ - 1];
    }
};

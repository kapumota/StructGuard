#include "Stack.hpp"

namespace demo {

template <class T>
Stack<T>::Stack() : data{}, n(0) {}

template <class T>
void Stack<T>::push(const T& value) {
    data[n] = value;
    n += 1;
}

template <class T>
T Stack<T>::pop() {
    n -= 1;
    return data[n];
}

template <class T>
T Stack<T>::top() const {
    return data[n - 1];
}

template <class T>
T Stack<T>::peek() const {
    return top();
}

template <class T>
int Stack<T>::size() const {
    return n;
}

template class Stack<int>;

}  // namespace demo

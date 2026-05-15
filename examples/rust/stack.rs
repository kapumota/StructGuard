pub struct Stack { n: i32 }

// invariant: n >= 0
impl Stack {
    // ensures: n == 0
    pub fn new() -> Self { Stack { n: 0 } }
    // ensures: n == old(n) + 1
    pub fn push(&mut self, _x: i32) { self.n += 1; }
    // requires: n > 0
    // ensures: n == old(n) - 1
    pub fn pop(&mut self) -> i32 { self.n -= 1; 0 }
}

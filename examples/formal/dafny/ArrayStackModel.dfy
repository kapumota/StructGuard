// Ejemplo de referencia generado por StructGuard para formal.dafny.ArrayStack
// Backend Dafny experimental: modelo abstracto, no traducción de C++ real.
trait ArrayStackModel {
  ghost var n: int
  ghost var capacity: int

  predicate Valid()
    reads this
  {
    n >= 0 &&
    n <= capacity
  }

  method add(i: int)
    requires Valid()
    requires 0 <= i && i <= n
    ensures Valid()
    ensures n == old(n) + 1

  method remove(i: int)
    requires Valid()
    requires 0 <= i && i < n
    ensures Valid()
    ensures n == old(n) - 1
}

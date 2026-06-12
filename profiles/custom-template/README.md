### Custom Template Profile

#### Propósito

Plantilla para crear perfiles propios de StructGuard.

#### Pasos recomendados

1. Copia esta carpeta con un nombre nuevo.
2. Edita `profile.yml`.
3. Agrega contratos `.sgdsl` en `contracts/` dentro del perfil.
4. Ejecuta StructGuard con `scan --preset` y el perfil creado.

#### Uso esperado

```bash
cp -r profiles/custom-template profiles/my-course

structguard scan include \
  --profile my-course \
  --preset contracts \
  --headers-only \
  --contract profiles/my-course/contracts/custom_structure.sgdsl
```

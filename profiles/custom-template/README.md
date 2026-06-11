### Custom Template Profile

#### Proposito

Plantilla para crear perfiles propios de StructGuard.

#### Pasos recomendados

1. Copia esta carpeta con un nombre nuevo.
2. Edita `profile.yml`.
3. Agrega contratos `.sgdsl` en `contracts/`.
4. Ejecuta StructGuard con `--dsl` apuntando a los contratos del perfil.

#### Uso esperado

```bash
cp -r profiles/custom-template profiles/my-course
structguard analyze include   --headers-only   --dsl profiles/my-course/contracts/custom_structure.sgdsl
```

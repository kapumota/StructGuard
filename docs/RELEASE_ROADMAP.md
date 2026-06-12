### Roadmap posterior a Fase 19

#### Estado actual

Después de Fase 19, StructGuard queda con:

```text
CLI canónico basado en scan --preset
report derive para reportes derivados
TestGen como reemplazo público de fuzz
benchmark en CI
smoke test de usuario nuevo
módulos legacy documentados
contratos ubicados en profiles/*/contracts/
```

#### Fase 20: tag, release y publicación

La Fase 20 debe cerrar el primer ciclo estable del proyecto. No debe introducir cambios grandes de arquitectura.

Actividades recomendadas:

```text
validar main limpio
validar CI y benchmark en verde
validar pytest, ruff y mypy
crear tag anotado v1.0.0
crear GitHub Release sobre v1.0.0
confirmar badges públicos del README
copiar resumen del CHANGELOG al release
marcar la versión como estable si no hay workflows fallando
```

Comandos sugeridos:

```bash
git checkout main
git pull origin main
git status --short

pytest -q
ruff check .
mypy
bash scripts/smoke_new_user.sh
python benchmarks/run_benchmark.py --fail-on-threshold

git tag -a v1.0.0 -m "release v1.0.0: StructGuard estable con perfiles, CI y contratos canónicos"
git push origin main --tags
```

#### Badges esperados

El README debe mostrar badges para:

```text
StructGuard CI
Benchmark
Release
License
```

El badge de release puede mostrar un estado vacío hasta que exista el primer GitHub Release.

#### Fases posteriores

```text
Fase 21: empaquetado Python y publicación opcional
Fase 22: guías de contribución avanzada
Fase 23: expansión de perfiles educativos y estructuras avanzadas
Fase 24: endurecimiento del backend formal y evidencia reproducible
```

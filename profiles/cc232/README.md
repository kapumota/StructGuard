### Perfil CC-232

#### Propósito

Este perfil agrupa contratos y configuración para estructuras de datos usadas en CC-232.

La ruta canónica del contrato principal es:

```text
profiles/cc232/contracts/cc232_core.sgdsl
```

Dentro de `profiles/cc232/profile.yml`, la ruta aparece como `contracts/cc232_core.sgdsl` porque se resuelve de forma relativa al directorio del perfil.

#### Uso recomendado

```bash
structguard profiles validate profiles/cc232/profile.yml

structguard scan ../Libreria_cc232/Semana2/include \
  --profile cc232 \
  --preset ci \
  --headers-only \
  --report-json report/cc232_report.json
```

#### Estado

```text
Estado: académico
Ruta canónica: profiles/cc232/contracts/cc232_core.sgdsl
```

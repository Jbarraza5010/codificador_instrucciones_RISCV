# Codificador Educativo de Instrucciones RISC-V

Traduce una instruccion del subconjunto RV32I a su codificación binaria de
32 bits, mostrando el desglose de cada campo del formato correspondiente
(R, I, S o B) y el significado de cada uno.

## Preparación del entorno

Se requiere unicamente **Python 3**.
La herramienta usa exclusivamente la biblioteca estandar de Python.
No hay dependencias que instalar, ni `requirements.txt`, ni entorno virtual.

Un único paso adicional, para dar permiso de ejecución al punto de entrada:

```bash
chmod +x run.sh
```

Con eso el entorno queda listo.

## Uso

```bash
./run.sh "add x5, x6, x7"
```

## Instrucciones soportadas

| Formato | Instrucciones |
|---|---|
| R | `add`, `sub`, `and`, `or` |
| I | `addi`, `andi` |
| I (carga) | `lb`, `lw` |
| S | `sb`, `sw` |
| B | `beq`, `bne` |

Los registros se escriben unicamente en la forma `xN`, con N entre 0 y 31.
Los inmediatos y desplazamientos se pasan ya resueltos como valores
numéricos decimales. Además no se soportan etiquetas.

## Estructura del repositorio

```
run.sh                    punto de entrada
src/encoder.py            codificador
tests/casos.txt           36 casos de prueba (12 instrucciones x 3 escenarios)
tools/validar.py          valida los casos contra el toolchain oficial
evidencia/resultados.md   tabla de comparacion generada por tools/validar.py
docs/documentacion.md     documentacion tecnica
```

## Documentación

La documentacion tecnica completa —arquitectura, fuentes de los campos de
codificacion, ejemplos de salida por formato, evidencia de la validacion e
instalacion del toolchain— esta en [`docs/documentacion.md`](docs/documentacion.md).

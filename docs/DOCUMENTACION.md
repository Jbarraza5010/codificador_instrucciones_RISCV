# Documentación técnica

## 1. Instrucciones soportadas y origen de sus campos

### 1.1 Fuente consultada

Todos los valores de `opcode`, `funct3` y `funct7` se tomaron de:

> A. Waterman y K. Asanovic (eds.), *The RISC-V Instruction Set Manual,
> Volume I: Unprivileged ISA*, Document Version 20191213, RISC-V Foundation,
> diciembre de 2019.

Dentro de ese documento se consultaron dos partes distintas:

- **Los diagramas de formato** (capitulo *RV32I Base Integer Instruction Set*,
  secciones de instrucciones aritmeticas registro-registro, con inmediato,
  de carga y almacenamiento, y de saltos condicionales). De ahí salen los
  rangos de bits de cada campo y la partición del inmediato en los formatos
  S y B.
- **La tabla de listado de instrucciones** (*RV32I Base Instruction Set*, en
  el capitulo de listados al final del manual). De ahí salen los valores
  numéricos concretos de cada campo constante.

### 1.2 Tabla de codificación

| Instrucción | Formato | opcode | funct3 | funct7 |
|---|---|---|---|---|
| `add`  | R | `0110011` | `000` | `0000000` |
| `sub`  | R | `0110011` | `000` | `0100000` |
| `and`  | R | `0110011` | `111` | `0000000` |
| `or`   | R | `0110011` | `110` | `0000000` |
| `addi` | I | `0010011` | `000` | — |
| `andi` | I | `0010011` | `111` | — |
| `lb`   | I (carga) | `0000011` | `000` | — |
| `lw`   | I (carga) | `0000011` | `010` | — |
| `sb`   | S | `0100011` | `000` | — |
| `sw`   | S | `0100011` | `010` | — |
| `beq`  | B | `1100011` | `000` | — |
| `bne`  | B | `1100011` | `001` | — |

La tabla se implementa mediante un único diccionario nombrado `ISA`, y se encuentra en
`src/encoder.py`.

## 2. Arquitectura del código y diseño del algoritmo

### 2.1 Flujo general

```
./run.sh "add x5, x6, x7"
     |
     |  run.sh valida que llegue un único argumento y lo pasa a encoder.py
     v
sys.argv[1]
     |
     v
parse_instruccion()
     |  1. normaliza (strip, lower)
     |  2. separa mnemonico y operandos
     |  3. busca el mnemonico en ISA -> obtiene el formato
     |  4. segun el formato, lee e interpreta cada operando
     |  5. valida rangos
     |  6. llama a campos_r / campos_i / campos_s / campos_b
     v
LISTA DE CAMPOS  ->  (nombre, bit_alto, bit_bajo, valor, descripcion)
     |
     +----------------+------------------+------------------+
     v                v                  v                  v
 ensamblar()     linea binaria      tabla de campos     explicación
 -> 32 bits      -> HEX             -> bits y decimal   -> texto
```

### 2.2 Estructura intermedia: lista de campos

Antes de producir ninguna salida, el programa reduce la instrucción a una
única estructura **lista de campos**, donde cada campo es una tupla de
cinco elementos que dice qué valor va en qué bits y qué significa.

```python
("rs1", 19, 15, 6, "x6: primer operando fuente de la suma")
```

Los campos se listan en orden del bit 31 hacia el bit 0, siguiendo el mismo 
orden en definido por el manual referenciado. Una vez armada, el resto
del programa ya no necesita saber de qué instrucción se trata ni cómo estaba
escrita: las cuatro salidas —la cadena binaria, el hexadecimal, la tabla de
campos y la explicación— son cuatro recorridos de la misma lista. Por eso no
pueden contradecirse entre sí.

### 2.3 Lectura e interpretación de los operandos

`parse_instruccion` quita los espacios de los extremos y pasa a minúsculas utilizando 
los comandos `.split()` y `.lower`, corta la línea para obtener la instrucción, y
busca ese mnemónico en el diccionario `ISA`. La tabla devuelve el formato y
los valores constantes de la instrucción: opcode, `funct3` y `funct7`. 

El resto de la línea se parte por comas de la siguiente forma:

```
operandos = [op.strip() for op in resto.split(",")] if resto else []
```

El formato determina cómo se interpreta la lista de operandos:

| Formato | Operandos | Interpretación |
|---|---|---|
| R | 3 | `rd`, `rs1`, `rs2`, los tres registros |
| I | 3 | `rd`, `rs1`, e inmediato |
| I (carga) | 2 | `rd`, y `imm(rs1)` descompuesto |
| S | 2 | `rs2`, y `imm(rs1)` descompuesto |
| B | 3 | `rs1`, `rs2`, y desplazamiento |

Las cargas (`lb`, `lw`) usan el mismo layout de bits que `addi` y `andi`, 
pero se escriben con paréntesis. El programa las marca en el conjunto `CARGAS` 
para leer sus operandos de otra forma, aunque el formato que reporta sigue siendo `I`.

Antes de construir los campos se validan los rangos con `check_rango` y se realiza 
antes de cualquier operación que utilice una máscara. 

### 2.4 Construcción de campos

Hay una función por formato las cuales son: `campos_r`, `campos_i`, `campos_s`, `campos_b`—
y las cuatro devuelven la misma estructura. En los formatos R e I cada cadena de bits
perteneciente a un registro o inmediato se reparte de forma completa en su campo correspondiente
dentro de la instrucción. En los casos de S y B el inmediato debe repartirse según indica
el diagrama de formato correspondiente.

En el formato S se parte en dos: los siete bits mas significativos ocupan las posiciones
31:25 y los cinco menos significativos el hueco donde en el formato R estaría `rd`.

El formato B es el único cuyo inmediato queda en cuatro trozos no contiguos:

```
imm >> 12  ->  bit 31       (imm[12], el bit de signo)
imm >>  5  ->  bits 30:25   (imm[10:5])
imm >>  1  ->  bits 11:8    (imm[4:1])
imm >> 11  ->  bit 7        (imm[11])
```

El bit 0 no se almacena porque las instrucciones ocupan direcciones pares, de
modo que todo desplazamiento de salto es par y ese bit siempre valdría cero.

### 2.5 Ensamblado de la palabra de 32 bits

El ensamblado es un único bucle que recibe el cada valor de la instrucción 
y determina la posición del bits donde se ubica, para finalmente concatenarlos 
en su orden correspondiente.

```python
for _, hi, lo, valor, _ in campos:
    ancho = hi - lo + 1
    bits += format(valor & ((1 << ancho) - 1), f"0{ancho}b")
```

La expresión `(1 << ancho) - 1` construye la máscara del campo la cúal
equivale al tamaño de bits del rango del campo. El `&` con esa máscara recorta el
valor a ese ancho.

Esa misma máscara resuelve los inmediatos negativos debido a como
Python interpreta los número negativos. Por ejemplo en `sw x8, -4(x2)`,
el campo`imm[11:5]` recibe el valor `-4 >> 5`, que es `-1`, y la máscara 
de siete bits lo convierte en `1111111`.

### 2.6 Generación de la salida

La función `imprimir` recorre la lista de campos para producir las cuatro
partes de la salida. La cadena binaria ya viene armada por el ensamblador y se
convierte a entero con `int(bits, 2)` para obtener el hexadecimal. La tabla de
campos recorre **lista de campos** haciendo que cada valor corresponda al rango 
de su campo, y la explicación recorre la misma lista leyendo la descripción de cada tupla.

### 2.7 Manejo de errores

Todas las validaciones lanzan la excepción `ErrorCodificacion`, que
`main()` atrapa en un unico punto. El mensaje va a **stderr** y el programa
termina con código de salida 1. Además, dentro de cada función se agregan mensajes 
de error correspondientes al propósito de la función.

## 3. Ejemplos de salida

### 3.1 Formato R — `add x5, x6, x7`

```
Instruccion: add x5, x6, x7
Formato: R

Binario: 00000000011100110000001010110011
HEX: 0x007302b3

Campos:
  funct7  [31:25] = 0000000  decimal: 0
  rs2     [24:20] = 00111    decimal: 7
  rs1     [19:15] = 00110    decimal: 6
  funct3  [14:12] = 000      decimal: 0
  rd      [11:7]  = 00101    decimal: 5
  opcode  [6:0]   = 0110011  decimal: 51

Explicacion:
  funct7  0000000: identifica ADD
  rs2     x7: segundo registro de suma
  rs1     x6: primer registro de suma
  funct3  junto a funct7 selecciona suma
  rd      x5: registro destino
  opcode  OP: operación registro-registro
```

### 3.2 Formato I — `addi x10, x1, -12`

```
Instruccion: addi x10, x1, -12
Formato: I

Binario: 11111111010000001000010100010011
HEX: 0xff408513

Campos:
  imm[11:0]  [31:20] = 111111110100  decimal: 4084
  rs1        [19:15] = 00001         decimal: 1
  funct3     [14:12] = 000           decimal: 0
  rd         [11:7]  = 01010         decimal: 10
  opcode     [6:0]   = 0010011       decimal: 19

Explicacion:
  imm[11:0]  -12: constante operando de suma
  rs1        x1: registro operando de suma
  funct3     selecciona la operación: suma
  rd         x10: registro destino
  opcode     OP-IMM: operación con inmediato
```

El campo `imm[11:0]` muestra `decimal: 4084` porque esa columna reporta el
valor del **campo de bits**, no el del inmediato original. `4084` es la
representacion en complemento a dos de `-12` sobre 12 bits
(`4096 - 12 = 4084`). El valor con signo aparece en la explicacion.

### 3.3 Formato S — `sw x8, -4(x2)`

```
Instruccion: sw x8, -4(x2)
Formato: S

Binario: 11111110100000010010111000100011
HEX: 0xfe812e23

Campos:
  imm[11:5]  [31:25] = 1111111  decimal: 127
  rs2        [24:20] = 01000    decimal: 8
  rs1        [19:15] = 00010    decimal: 2
  funct3     [14:12] = 010      decimal: 2
  imm[4:0]   [11:7]  = 11100    decimal: 28
  opcode     [6:0]   = 0100011  decimal: 35

Explicacion:
  imm[11:5]  bits altos del desplazamiento -4 respecto a la base
  rs2        x8: registro cuyo valor se escribe en memoria
  rs1        x2: registro base de la dirección de memoria
  funct3     ancho del acceso: palabra de 32 bits
  imm[4:0]   bits bajos del desplazamiento -4
  opcode     STORE: almacenamiento en memoria
```

### 3.4 Formato B — `bne x1, x2, -4`

```
Instruccion: bne x1, x2, -4
Formato: B

Binario: 11111110001000001001111011100011
HEX: 0xfe209ee3

Campos:
  imm[12]    [31]    = 1        decimal: 1
  imm[10:5]  [30:25] = 111111   decimal: 63
  rs2        [24:20] = 00010    decimal: 2
  rs1        [19:15] = 00001    decimal: 1
  funct3     [14:12] = 001      decimal: 1
  imm[4:1]   [11:8]  = 1110     decimal: 14
  imm[11]    [7]     = 1        decimal: 1
  opcode     [6:0]   = 1100011  decimal: 99

Explicacion:
  imm[12]    bit de signo del desplazamiento -4
  imm[10:5]  bits 10:5 del desplazamiento -4
  rs2        x2: segundo registro de la comparación
  rs1        x1: primer registro de la comparación
  funct3     selecciona la condición: salta si x1 y x2 son distintos
  imm[4:1]   bits 4:1 del desplazamiento; el bit 0 es implícito y no se almacena
  imm[11]    bit 11 del desplazamiento -4
  opcode     BRANCH: salto condicional
```

## 4. Validación contra el toolchain 

### 4.1 Metodología

Se construyeron 36 casos de prueba (12 instrucciones x 3 escenarios),
listados en `tests/casos.txt`. Los escenarios cubren, segun aplique a cada
instrucción:

- valores positivos
- valores negativos
- valores limite

Para las cuatro instrucciones de tipo R no existe campo inmediato, por lo que
sus tres escenarios varian los registros cubriendo el caso normal, el uso de
`x0` y el uso de los registros mas altos.

El proceso de validación esta automatizado en `tools/validar.py`, que para
cada caso:

1. lo ensambla con el toolchain (`as -march=rv32i -mabi=ilp32`)
2. obtiene la codificación de referencia con `objdump -d`
3. ejecuta `./run.sh "<instruccion>"` y extrae la línea `HEX:`
4. compara ambas codificaciones
5. escribe la tabla completa en `evidencia/resultados.md`

Para reproducirlo:

```bash
python3 tools/validar.py
```

### 4.2 Resultado

36 de 36 casos coinciden con la codificación de referencia producida por
GNU binutils para `riscv64-unknown-elf` sobre objetos `elf32-littleriscv`.

La tabla completa de los resultados se encuentra en
[`evidencia/resultados.md`](../evidencia/resultados.md).

### 4.3 Interpretación del destino de los saltos

GNU `as` interpreta un número suelto en un salto como una dirección
absoluta donde `beq x1, x2, 8` significa para "saltar a la dirección 8". 
Al ensamblar los 36 casos en un mismo archivo, calcula el desplazamiento
restando la dirección actual y, expande el salto en dos instrucciones. 
El resultado eran 42 instrucciones desensambladas en lugar de 36, una de 
más por cada uno de los 6 saltos.

Este modelo, en cambio, interpreta ese número como el desplazamiento que se
codifica en el campo `imm` del formato B, que es lo que corresponde según la
especificación del proyecto: los operandos llegan ya resueltos y no hay que
resolver saltos relativos a etiquetas.

Para expresarle esa misma interpretación al ensamblador sin ambigüedad,
`tools/validar.py` reescribe el destino en el archivo `.s` usando la forma
relativa explícita, donde `.` denota la posición actual:

```
beq x1, x2, 8       ->   beq x1, x2, . + 8
beq x3, x4, -8      ->   beq x3, x4, . - 8
bne x11, x12, 4094  ->   bne x11, x12, . + 4094
```

## 5. Instalación del toolchain

Sobre Ubuntu/Debian, el ensamblador y el `objdump` para RISC-V de 32 bits
estan disponibles como paquete:

```bash
sudo apt update
sudo apt install binutils-riscv64-unknown-elf
```

La versión utilizada en esta validación: GNU binutils 2.35.1 (paquete
`binutils-riscv64-unknown-elf`, Ubuntu 22.04).

Comprobación:

```bash
riscv64-unknown-elf-as --version
riscv64-unknown-elf-objdump --version
```

Aunque el paquete se llama `riscv64`, el ensamblador acepta
`-march=rv32i -mabi=ilp32` y produce objetos `elf32-littleriscv`

`tools/validar.py` detecta automaticamente el prefijo del toolchain entre los
mas habituales (`riscv64-unknown-elf-`, `riscv32-unknown-elf-`,
`riscv64-linux-gnu-`).

## 6. Preparación de la herramienta

La herramienta requiere unicamente **Python 3** y usa
exclusivamente la biblioteca estándar: no hay dependencias que instalar, ni
`requirements.txt`, ni entorno virtual.

El unico paso de preparación es dar permiso de ejecución al punto de entrada:

```bash
chmod +x run.sh
```

## 7. Referencias

[1] A. Waterman y K. Asanovic (eds.), *The RISC-V Instruction Set Manual,
Volume I: Unprivileged ISA*, Document Version 20191213, RISC-V Foundation,
2019.

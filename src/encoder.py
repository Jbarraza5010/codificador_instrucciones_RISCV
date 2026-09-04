"""Codificador de instrucciones RISC-V RV32I.

Recibe una unica instrucción como argumento y muestra su codificacion de
32 bits, el desglose de los campos del formato correspondiente (R, I, S o B)
y el significado de cada campo.
"""

import re
import sys

# mnemonico -> (formato, opcode, funct3, funct7)

ISA = {
    "add":  ("R", 0b0110011, 0b000, 0b0000000),
    "sub":  ("R", 0b0110011, 0b000, 0b0100000),
    "and":  ("R", 0b0110011, 0b111, 0b0000000),
    "or":   ("R", 0b0110011, 0b110, 0b0000000),
    "addi": ("I", 0b0010011, 0b000, None),
    "andi": ("I", 0b0010011, 0b111, None),
    "lb":   ("I", 0b0000011, 0b000, None),
    "lw":   ("I", 0b0000011, 0b010, None),
    "sb":   ("S", 0b0100011, 0b000, None),
    "sw":   ("S", 0b0100011, 0b010, None),
    "beq":  ("B", 0b1100011, 0b000, None),
    "bne":  ("B", 0b1100011, 0b001, None),
}

CARGAS = {"lb", "lw"}  # subconjunto de formato I con sintaxis "rd, imm(rs1)"

REG_RE = re.compile(r"^x(\d{1,2})$")
MEM_RE = re.compile(r"^(-?\d+)\(\s*(x\d{1,2})\s*\)$")


class ErrorCodificacion(Exception):
    """Error de sintaxis o de rango al codificar la instrucción"""


def parse_reg(token: str) -> int:
    """Convierte un registro en un número entero"""
    m = REG_RE.match(token)
    if not m:
        raise ErrorCodificacion("registro inválido")
    n = int(m.group(1))
    if not 0 <= n <= 31:
        raise ErrorCodificacion("registro fuera de rango")
    return n


def parse_imm(token: str) -> int:
    """Convierte el texto de un inmediato en un entero con signo"""
    try:
        return int(token)
    except ValueError:
        raise ErrorCodificacion("inmediato inválido")


def parse_mem(token: str) -> tuple[int, int]:
    """Descompone el formato desplazamiento(registro) en un par (desplazamiento, registro)"""
    m = MEM_RE.match(token.strip())
    if not m:
        raise ErrorCodificacion("sintáxis inválida")
    return int(m.group(1)), parse_reg(m.group(2))


def check_rango(valor: int, bits: int, etiqueta: str) -> None:
    """Verifica que el valor quepa con signo en el numero de bits indicado"""
    lo = -(1 << (bits - 1))     # 12 bits -> -2048
    hi = (1 << (bits - 1)) - 1  # 12 bits ->  2047
    if not (lo <= valor <= hi):
        raise ErrorCodificacion(f"{etiqueta} fuera de rango [{lo}, {hi}]: {valor}")


# Una función por formato. Todas devuelven la misma estructura: una lista de
# campos (nombre, bit_alto, bit_bajo, valor, descripcion).
def campos_r(mnemonico, opcode, funct3, funct7, rd, rs1, rs2):
    """Arma los campos del formato R"""
    op_desc = {"add": "suma", "sub": "resta", "and": "operación AND", "or": "operación OR"}[mnemonico]
    if mnemonico == "add":
        desc_funct7 = "0000000: identifica ADD"
    elif mnemonico == "sub":
        desc_funct7 = "0100000: identifica SUB"
    else:
        desc_funct7 = "0000000: no se usa para distinguir variantes con este funct3"
    return [
        ("funct7", 31, 25, funct7, desc_funct7),
        ("rs2",    24, 20, rs2,    f"x{rs2}: segundo registro de {op_desc}"),
        ("rs1",    19, 15, rs1,    f"x{rs1}: primer registro de {op_desc}"),
        ("funct3", 14, 12, funct3, f"junto a funct7 selecciona {op_desc}"),
        ("rd",     11, 7,  rd,     f"x{rd}: registro destino"),
        ("opcode",  6, 0,  opcode, "OP: operación registro-registro"),
    ]


def campos_i(mnemonico, opcode, funct3, rd, rs1, imm):
    """Arma los campos del formato I: inmediato de 12 bits en la parte alta"""
    if mnemonico in CARGAS:
        ancho_desc = {"lb": "byte con extensión de signo", "lw": "palabra de 32 bits"}[mnemonico]
        return [
            ("imm[11:0]", 31, 20, imm, f"{imm}: desplazamiento sumado a x{rs1}"),
            ("rs1",       19, 15, rs1, f"x{rs1}: registro base de la dirección de memoria"),
            ("funct3",    14, 12, funct3, f"ancho del acceso: {ancho_desc}"),
            ("rd",        11, 7,  rd,  f"x{rd}: registro destino"),
            ("opcode",     6, 0,  opcode, "LOAD: lectura de memoria"),
        ]
    op_desc = {"addi": "suma", "andi": "operación AND"}[mnemonico]
    return [
        ("imm[11:0]", 31, 20, imm, f"{imm}: constante operando de {op_desc}"),
        ("rs1",       19, 15, rs1, f"x{rs1}: registro operando de {op_desc}"),
        ("funct3",    14, 12, funct3, f"selecciona la operación: {op_desc}"),
        ("rd",        11, 7,  rd,  f"x{rd}: registro destino"),
        ("opcode",     6, 0,  opcode, "OP-IMM: operación con inmediato"),
    ]


def campos_s(mnemonico, opcode, funct3, rs1, rs2, imm):
    """Arma los campos del formato S: el inmediato va partido en dos trozos"""
    ancho_desc = {"sb": "byte", "sw": "palabra de 32 bits"}[mnemonico]
    return [
        ("imm[11:5]", 31, 25, imm >> 5, f"bits altos del desplazamiento {imm} respecto a la base"),
        ("rs2",       24, 20, rs2,      f"x{rs2}: registro cuyo valor se escribe en memoria"),
        ("rs1",       19, 15, rs1,      f"x{rs1}: registro base de la dirección de memoria"),
        ("funct3",    14, 12, funct3,   f"ancho del acceso: {ancho_desc}"),
        ("imm[4:0]",  11, 7,  imm,      f"bits bajos del desplazamiento {imm}"),
        ("opcode",     6, 0,  opcode,   "STORE: almacenamiento en memoria"),
    ]


def campos_b(mnemonico, opcode, funct3, rs1, rs2, imm):
    """Arma los campos del formato B: el desplazamiento va en cuatro trozos"""
    cond_desc = {"beq": "son iguales", "bne": "son distintos"}[mnemonico]
    return [
        ("imm[12]",   31, 31, imm >> 12, f"bit de signo del desplazamiento {imm}"),
        ("imm[10:5]", 30, 25, imm >> 5,  f"bits 10:5 del desplazamiento {imm}"),
        ("rs2",       24, 20, rs2,       f"x{rs2}: segundo registro de la comparación"),
        ("rs1",       19, 15, rs1,       f"x{rs1}: primer registro de la comparación"),
        ("funct3",    14, 12, funct3,    f"selecciona la condición: salta si x{rs1} y x{rs2} {cond_desc}"),
        ("imm[4:1]",  11, 8,  imm >> 1,  "bits 4:1 del desplazamiento; el bit 0 es implícito y no se almacena"),
        ("imm[11]",    7, 7,  imm >> 11, f"bit 11 del desplazamiento {imm}"),
        ("opcode",     6, 0,  opcode,    "BRANCH: salto condicional"),
    ]


def parse_instruccion(linea: str):
    """Traduce el texto de la instrucción a (formato, lista de campos)"""
    # Elimina espacios al principio y al final, y pasa a minusculas
    linea = linea.strip().lower()
    if not linea:
        raise ErrorCodificacion("instrucción vacía")

    # Separa el mnemonico del resto de la instrucción
    partes = linea.split(None, 1)
    mnemonico = partes[0]
    resto = partes[1] if len(partes) > 1 else ""
    if mnemonico not in ISA:
        raise ErrorCodificacion(
            "instrucción no soportada"
        )
    
    fmt, opcode, funct3, funct7 = ISA[mnemonico]
    # Parte los operandos por comas, eliminando espacios alrededor de cada uno
    operandos = [op.strip() for op in resto.split(",")] if resto else []

    # Segun el formato interpreta los operandos y arma los campos de la instruccion
    if fmt == "R":
        if len(operandos) != 3:
            raise ErrorCodificacion("espera 3 operandos: rd, rs1, rs2")
        rd, rs1, rs2 = (parse_reg(t) for t in operandos)
        campos = campos_r(mnemonico, opcode, funct3, funct7, rd, rs1, rs2)

    elif fmt == "I" and mnemonico in CARGAS:
        if len(operandos) != 2:
            raise ErrorCodificacion("espera 2 operandos: rd, imm(rs1)")
        rd = parse_reg(operandos[0])
        imm, rs1 = parse_mem(operandos[1])
        check_rango(imm, 12, "el inmediato")
        campos = campos_i(mnemonico, opcode, funct3, rd, rs1, imm)

    elif fmt == "I":
        if len(operandos) != 3:
            raise ErrorCodificacion("espera 3 operandos: rd, rs1, imm")
        rd = parse_reg(operandos[0])
        rs1 = parse_reg(operandos[1])
        imm = parse_imm(operandos[2])
        check_rango(imm, 12, "el inmediato")
        campos = campos_i(mnemonico, opcode, funct3, rd, rs1, imm)

    elif fmt == "S":
        if len(operandos) != 2:
            raise ErrorCodificacion("espera 2 operandos: rs2, imm(rs1)")
        rs2 = parse_reg(operandos[0])
        imm, rs1 = parse_mem(operandos[1])
        check_rango(imm, 12, "el inmediato")
        campos = campos_s(mnemonico, opcode, funct3, rs1, rs2, imm)

    else:  # fmt == "B"
        if len(operandos) != 3:
            raise ErrorCodificacion("espera 3 operandos: rs1, rs2, imm")
        rs1 = parse_reg(operandos[0])
        rs2 = parse_reg(operandos[1])
        imm = parse_imm(operandos[2])
        if imm % 2 != 0:
            raise ErrorCodificacion("el desplazamiento debe ser par")
        check_rango(imm, 13, "el desplazamiento")
        campos = campos_b(mnemonico, opcode, funct3, rs1, rs2, imm)

    return fmt, campos


def ensamblar(campos) -> str:
    """Concatena los campos en la cadena de 32 bits, de bit 31 hacia 0"""
    bits = ""
    for _, hi, lo, valor, _ in campos:
        ancho = hi - lo + 1
        # (1 << ancho) - 1 es la mascara del campo
        bits += format(valor & ((1 << ancho) - 1), f"0{ancho}b")
    return bits


def bracket(hi: int, lo: int) -> str:
    """Formatea el rango de bits de un campo: [31:25] o [7] """
    return f"[{hi}]" if hi == lo else f"[{hi}:{lo}]"


def imprimir(texto: str, fmt: str, bits: str, campos) -> None:
    """Muestra en consola el binario, el hex, los campos y su explicación"""
    palabra = int(bits, 2)   
    print(f"Instruccion: {texto}")
    print(f"Formato: {fmt}")
    print()
    print(f"Binario: {bits}")
    print(f"HEX: 0x{palabra:08x}")
    print()
    print("Campos:")
    # Anchos de columna calculados a partir del contenido mas largo
    nombre_w = max(len(nombre) for nombre, _, _, _, _ in campos) + 2
    bracket_w = max(len(bracket(hi, lo)) for _, hi, lo, _, _ in campos)
    bin_w = max(hi - lo + 1 for _, hi, lo, _, _ in campos)
    for nombre, hi, lo, valor, _ in campos:
        ancho = hi - lo + 1
        crudo = valor & ((1 << ancho) - 1)
        binvalue = format(crudo, f"0{ancho}b")
        print(f"  {nombre:<{nombre_w}}{bracket(hi, lo):<{bracket_w}} = "
              f"{binvalue:<{bin_w}}  decimal: {crudo}")
    print()
    print("Explicacion:")
    for nombre, _, _, _, desc in campos:
        print(f"  {nombre:<{nombre_w}}{desc}")


def main() -> None:
    """Lee la instrucción en ensamblador y la codifica"""
    if len(sys.argv) != 2:
        sys.exit(2)

    texto = sys.argv[1]
    try:
        fmt, campos = parse_instruccion(texto)
        bits = ensamblar(campos)
    except ErrorCodificacion as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    imprimir(texto, fmt, bits, campos)


if __name__ == "__main__":
    main()

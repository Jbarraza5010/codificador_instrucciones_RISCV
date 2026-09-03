#!/usr/bin/env python3
"""Codificador de instrucciones RISC-V RV32I.

Para probar otra instruccion, editar la variable de abajo y volver a correr:
    python3 encoder.py
"""

import re
import sys

instruccion = "and x13, x3, x4"

# ---------------------------------------------------------------------------
# Unica fuente de valores de la ISA. Nada mas en este archivo conoce
# opcode/funct3/funct7.
#
# Fuente: Waterman & Asanovic, "The RISC-V Instruction Set Manual, Volume I:
# Unprivileged ISA", Document Version 20191213, tabla "RV32I Base Instruction
# Set".
#
# mnemonico -> (formato, opcode, funct3, funct7)   funct7 es None si no aplica
# ---------------------------------------------------------------------------
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
    """Error de sintaxis o de rango al codificar la instruccion."""


def parse_reg(token: str) -> int:
    m = REG_RE.match(token)
    if not m:
        raise ErrorCodificacion(f"registro invalido: '{token}' (se esperaba xN)")
    n = int(m.group(1))
    if not 0 <= n <= 31:
        raise ErrorCodificacion(f"registro fuera de rango: '{token}' (debe ser x0-x31)")
    return n


def parse_imm(token: str) -> int:
    try:
        return int(token)
    except ValueError:
        raise ErrorCodificacion(f"inmediato invalido: '{token}'")


def parse_mem(token: str) -> tuple[int, int]:
    m = MEM_RE.match(token.strip())
    if not m:
        raise ErrorCodificacion(f"sintaxis invalida, se esperaba 'imm(xN)': '{token}'")
    return int(m.group(1)), parse_reg(m.group(2))


def check_rango(valor: int, bits: int, etiqueta: str) -> None:
    """Valida el rango ANTES de enmascarar; despues de la mascara ya no
    se puede distinguir un valor fuera de rango de uno valido."""
    lo = -(1 << (bits - 1))
    hi = (1 << (bits - 1)) - 1
    if not (lo <= valor <= hi):
        raise ErrorCodificacion(f"{etiqueta} fuera de rango [{lo}, {hi}]: {valor}")


# ---------------------------------------------------------------------------
# Una funcion por formato. Cada una devuelve la lista de campos
# (nombre, bit_alto, bit_bajo, valor, descripcion) de la que salen despues
# el binario, el hex, el desglose y la explicacion (una sola fuente de verdad).
# ---------------------------------------------------------------------------
def campos_r(mnemonico, opcode, funct3, funct7, rd, rs1, rs2):
    op_desc = {"add": "la suma", "sub": "la resta", "and": "el AND logico", "or": "el OR logico"}[mnemonico]
    if mnemonico == "add":
        desc_funct7 = "0000000: identifica ADD (SUB usa 0100000 con el mismo opcode y funct3)"
    elif mnemonico == "sub":
        desc_funct7 = "0100000 distingue SUB de ADD (que usa 0000000)"
    else:
        desc_funct7 = "0000000: no se usa para distinguir variantes con este funct3"
    return [
        ("funct7", 31, 25, funct7, desc_funct7),
        ("rs2",    24, 20, rs2,    f"x{rs2}: segundo operando fuente de {op_desc}"),
        ("rs1",    19, 15, rs1,    f"x{rs1}: primer operando fuente de {op_desc}"),
        ("funct3", 14, 12, funct3, f"junto a funct7 selecciona {op_desc}"),
        ("rd",     11, 7,  rd,     f"x{rd}: registro destino, recibe el resultado de {op_desc}"),
        ("opcode",  6, 0,  opcode, "OP: operacion registro-registro (ALU)"),
    ]


def campos_i(mnemonico, opcode, funct3, rd, rs1, imm):
    if mnemonico in CARGAS:
        ancho_desc = {"lb": "un byte con extension de signo", "lw": "una palabra de 32 bits"}[mnemonico]
        return [
            ("imm[11:0]", 31, 20, imm, f"{imm}: desplazamiento con signo sumado a x{rs1} para formar la direccion de memoria"),
            ("rs1",       19, 15, rs1, f"x{rs1}: registro base de la direccion de memoria"),
            ("funct3",    14, 12, funct3, f"ancho del acceso: {mnemonico} carga {ancho_desc}"),
            ("rd",        11, 7,  rd,  f"x{rd}: registro destino, recibe el dato leido de memoria"),
            ("opcode",     6, 0,  opcode, "LOAD: lectura de memoria"),
        ]
    op_desc = {"addi": "la suma", "andi": "el AND logico"}[mnemonico]
    return [
        ("imm[11:0]", 31, 20, imm, f"{imm}: constante con signo extendida a 32 bits, operando de {op_desc}"),
        ("rs1",       19, 15, rs1, f"x{rs1}: operando fuente de {op_desc}"),
        ("funct3",    14, 12, funct3, f"selecciona la operacion: {op_desc}"),
        ("rd",        11, 7,  rd,  f"x{rd}: registro destino, recibe el resultado de {op_desc}"),
        ("opcode",     6, 0,  opcode, "OP-IMM: operacion con inmediato"),
    ]


def campos_s(mnemonico, opcode, funct3, rs1, rs2, imm):
    ancho_desc = {"sb": "un byte", "sw": "una palabra de 32 bits"}[mnemonico]
    return [
        ("imm[11:5]", 31, 25, imm >> 5, f"bits altos del desplazamiento {imm} respecto a la base"),
        ("rs2",       24, 20, rs2,      f"x{rs2}: registro cuyo valor se escribe en memoria"),
        ("rs1",       19, 15, rs1,      f"x{rs1}: registro base de la direccion de memoria"),
        ("funct3",    14, 12, funct3,   f"ancho del acceso: {mnemonico} guarda {ancho_desc}"),
        ("imm[4:0]",  11, 7,  imm,      f"bits bajos del desplazamiento {imm}"),
        ("opcode",     6, 0,  opcode,   "STORE: almacenamiento en memoria"),
    ]


def campos_b(mnemonico, opcode, funct3, rs1, rs2, imm):
    cond_desc = {"beq": "son iguales", "bne": "son distintos"}[mnemonico]
    return [
        ("imm[12]",   31, 31, imm >> 12, f"bit de signo del desplazamiento {imm}"),
        ("imm[10:5]", 30, 25, imm >> 5,  f"bits 10:5 del desplazamiento {imm}"),
        ("rs2",       24, 20, rs2,       f"x{rs2}: segundo operando de la comparacion"),
        ("rs1",       19, 15, rs1,       f"x{rs1}: primer operando de la comparacion"),
        ("funct3",    14, 12, funct3,    f"selecciona la condicion: {mnemonico} salta si x{rs1} y x{rs2} {cond_desc}"),
        ("imm[4:1]",  11, 8,  imm >> 1,  "bits 4:1 del desplazamiento; el bit 0 es implicito (siempre 0) y no se almacena"),
        ("imm[11]",    7, 7,  imm >> 11, f"bit 11 del desplazamiento {imm}, junto al opcode"),
        ("opcode",     6, 0,  opcode,    "BRANCH: salto condicional"),
    ]


def parse_instruccion(linea: str):
    """Parsea una linea de ensamblador y devuelve (mnemonico, formato, campos)."""
    linea = linea.strip().lower()
    if not linea:
        raise ErrorCodificacion("instruccion vacia")

    partes = linea.split(None, 1)
    mnemonico = partes[0]
    resto = partes[1] if len(partes) > 1 else ""
    if mnemonico not in ISA:
        raise ErrorCodificacion(
            f"instruccion no soportada: '{mnemonico}' (validas: {', '.join(sorted(ISA))})"
        )
    fmt, opcode, funct3, funct7 = ISA[mnemonico]
    operandos = [op.strip() for op in resto.split(",")] if resto else []

    if fmt == "R":
        if len(operandos) != 3:
            raise ErrorCodificacion(f"{mnemonico} espera 3 operandos: rd, rs1, rs2")
        rd, rs1, rs2 = (parse_reg(t) for t in operandos)
        campos = campos_r(mnemonico, opcode, funct3, funct7, rd, rs1, rs2)

    elif fmt == "I" and mnemonico in CARGAS:
        if len(operandos) != 2:
            raise ErrorCodificacion(f"{mnemonico} espera 2 operandos: rd, imm(rs1)")
        rd = parse_reg(operandos[0])
        imm, rs1 = parse_mem(operandos[1])
        check_rango(imm, 12, "el inmediato")
        campos = campos_i(mnemonico, opcode, funct3, rd, rs1, imm)

    elif fmt == "I":
        if len(operandos) != 3:
            raise ErrorCodificacion(f"{mnemonico} espera 3 operandos: rd, rs1, imm")
        rd = parse_reg(operandos[0])
        rs1 = parse_reg(operandos[1])
        imm = parse_imm(operandos[2])
        check_rango(imm, 12, "el inmediato")
        campos = campos_i(mnemonico, opcode, funct3, rd, rs1, imm)

    elif fmt == "S":
        if len(operandos) != 2:
            raise ErrorCodificacion(f"{mnemonico} espera 2 operandos: rs2, imm(rs1)")
        rs2 = parse_reg(operandos[0])
        imm, rs1 = parse_mem(operandos[1])
        check_rango(imm, 12, "el inmediato")
        campos = campos_s(mnemonico, opcode, funct3, rs1, rs2, imm)

    else:  # fmt == "B"
        if len(operandos) != 3:
            raise ErrorCodificacion(f"{mnemonico} espera 3 operandos: rs1, rs2, imm")
        rs1 = parse_reg(operandos[0])
        rs2 = parse_reg(operandos[1])
        imm = parse_imm(operandos[2])
        if imm % 2 != 0:
            raise ErrorCodificacion(f"el desplazamiento debe ser par (bit 0 implicito): {imm}")
        check_rango(imm, 13, "el desplazamiento")
        campos = campos_b(mnemonico, opcode, funct3, rs1, rs2, imm)

    return fmt, campos


def ensamblar(campos) -> str:
    bits = ""
    for _, hi, lo, valor, _ in campos:
        ancho = hi - lo + 1
        bits += format(valor & ((1 << ancho) - 1), f"0{ancho}b")
    return bits


def bracket(hi: int, lo: int) -> str:
    return f"[{hi}]" if hi == lo else f"[{hi}:{lo}]"


def imprimir(texto: str, fmt: str, bits: int, campos) -> None:
    palabra = int(bits, 2)  
    print(f"Instruccion: {texto}")
    print(f"Formato: {fmt}")
    print()
    print(f"Binario: {bits}")
    print(f"HEX: 0x{palabra:08X}")
    print()
    print("Campos:")
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
    texto = sys.argv[1] if len(sys.argv) > 1 else instruccion
    try:
        fmt, campos = parse_instruccion(texto)
        bits = ensamblar(campos)
    except ErrorCodificacion as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    imprimir(texto, fmt, bits, campos)


if __name__ == "__main__":
    main()

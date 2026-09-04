"""Valida encoder.py contra un toolchain oficial de RISC-V (rv32).

Para cada caso de tests/casos.txt:
  1. lo ensambla con el toolchain oficial,
  2. obtiene la codificacion de referencia con `objdump -d`,
  3. ejecuta ./run.sh con la misma instruccion,
  4. compara ambas codificaciones,
  5. escribe la tabla de evidencia en evidencia/resultados.md

"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "casos.txt"
BUILD = RAIZ / "build"
SALIDA = RAIZ / "evidencia" / "resultados.md"
RUN_SH = RAIZ / "run.sh"

PREFIJOS = [
    "riscv64-unknown-elf-",
    "riscv32-unknown-elf-",
    "riscv-none-elf-",
    "riscv64-linux-gnu-",
    "riscv32-linux-gnu-",
    "riscv64-elf-",
    "riscv32-elf-",
]


def detectar_toolchain():
    """Devuelve (comando_ensamblar, comando_objdump, descripcion)"""
    prefijo = os.environ.get("PREFIX")
    candidatos = [prefijo] if prefijo else PREFIJOS
    for p in candidatos:
        if p and shutil.which(p + "as") and shutil.which(p + "objdump"):
            return ([p + "as", "-march=rv32i", "-mabi=ilp32"],
                    [p + "objdump", "-d"],
                    f"GNU binutils ({p})")
    if shutil.which("clang") and shutil.which("llvm-objdump"):
        return (["clang", "--target=riscv32", "-march=rv32i", "-c"],
                ["llvm-objdump", "-d", "--triple=riscv32"],
                "LLVM (clang + llvm-objdump)")
    return None, None, None


RAMAS = {"beq", "bne"}


def a_ensamblador(instruccion: str) -> str:
    """Reescribe el destino de los saltos como desplazamiento relativo al PC"""
    mnemonico = instruccion.split()[0].lower()
    if mnemonico not in RAMAS:
        return instruccion
    cabeza, _, desplazamiento = instruccion.rpartition(",")
    n = int(desplazamiento.strip())
    signo = "+" if n >= 0 else "-"
    return f"{cabeza}, . {signo} {abs(n)}"


def leer_casos():
    casos = []
    for linea in CASOS.read_text().splitlines():
        linea = linea.split("#")[0].strip()
        if linea:
            casos.append(linea)
    return casos


def ensamblar_con_toolchain(casos, cmd_as, cmd_objdump):
    """Ensambla todos los casos y devuelve la lista de palabras en hex"""
    BUILD.mkdir(exist_ok=True)
    fuente = BUILD / "casos.s"
    objeto = BUILD / "casos.o"
    fuente.write_text("\n".join(a_ensamblador(c) for c in casos) + "\n")

    r = subprocess.run(cmd_as + ["-mno-relax", "-o", str(objeto), str(fuente)],
                       capture_output=True, text=True)
    if r.returncode != 0: 
        r = subprocess.run(cmd_as + ["-o", str(objeto), str(fuente)],
                           capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Error al ensamblar:\n{r.stderr}")

    r = subprocess.run(cmd_objdump + [str(objeto)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Error en objdump:\n{r.stderr}")

    return parsear_objdump(r.stdout), r.stdout


def parsear_objdump(texto):
    """Extrae las palabras de 32 bits del desensamblado"""
    palabras = []
    for linea in texto.splitlines():
        m = re.match(r"\s*[0-9a-f]+:\s+([0-9a-f ]+?)\s{2,}", linea)
        if not m:
            continue
        crudo = m.group(1).strip()
        if re.fullmatch(r"[0-9a-f]{8}", crudo):              
            palabras.append(crudo)
        elif re.fullmatch(r"([0-9a-f]{2} ){3}[0-9a-f]{2}", crudo):  
            b = crudo.split()
            palabras.append("".join(reversed(b)))            
    return palabras


def codificar_con_modelo(instruccion):
    """Ejecuta ./run.sh y extrae la linea HEX"""
    r = subprocess.run([str(RUN_SH), instruccion],
                       capture_output=True, text=True)
    for linea in r.stdout.splitlines():
        if linea.startswith("HEX: 0x"):
            return linea[len("HEX: 0x"):].strip().lower()
    return None


def main():
    cmd_as, cmd_objdump, descripcion = detectar_toolchain()
    if cmd_as is None:
        sys.exit(
            "No se encontro un toolchain RISC-V de 32 bits.\n"
            "Instale uno (as + objdump para rv32) o indique el prefijo:\n"
            "    PREFIX=riscv64-unknown-elf- python3 tools/validar.py"
        )
    print(f"Toolchain detectado: {descripcion}\n")

    casos = leer_casos()
    referencias, desensamblado = ensamblar_con_toolchain(
        casos, cmd_as, cmd_objdump)

    if len(referencias) != len(casos):
        print(desensamblado, file=sys.stderr)
        sys.exit(
            f"Se esperaban {len(casos)} instrucciones desensambladas, se "
            f"obtuvieron {len(referencias)}. Revise el desensamblado de "
            f"arriba: es probable que el ensamblador haya expandido algun "
            f"salto en mas de una instruccion."
        )

    filas = []
    fallos = 0
    for i, (instr, ref) in enumerate(zip(casos, referencias), 1):
        propio = codificar_con_modelo(instr)
        coincide = propio == ref
        if not coincide:
            fallos += 1
        filas.append((i, instr, propio or "ERROR", ref, coincide))
        marca = "OK  " if coincide else "FALLA"
        print(f"{marca} {i:>2}. {instr:<24} modelo=0x{propio}  "
              f"objdump=0x{ref}")

    print(f"\n{len(casos) - fallos}/{len(casos)} coinciden")

    escribir_evidencia(filas, descripcion, desensamblado, fallos)
    print(f"Evidencia escrita en {SALIDA.relative_to(RAIZ)}")
    return 1 if fallos else 0


def escribir_evidencia(filas, descripcion, desensamblado, fallos):
    SALIDA.parent.mkdir(exist_ok=True)
    total = len(filas)
    lineas = [
        "# Evidencia de validacion contra el toolchain oficial",
        "",
        f"Toolchain utilizado: **{descripcion}**",
        "",
        f"Resultado: **{total - fallos}/{total} casos coinciden**.",
        "",
        "Cada caso se ensamblo con el toolchain oficial para rv32, se obtuvo",
        "su codificacion de referencia con `objdump -d`, y se comparo contra",
        "la salida de `./run.sh \"<instruccion>\"`.",
        "",
        "| # | Instruccion | Modelo propio | objdump -d | Coincide |",
        "|---|---|---|---|---|",
    ]
    for i, instr, propio, ref, ok in filas:
        lineas.append(f"| {i} | `{instr}` | `0x{propio}` | `0x{ref}` | "
                      f"{'si' if ok else '**NO**'} |")
    lineas += [
        "",
        "## Salida completa de `objdump -d`",
        "",
        "```",
        desensamblado.rstrip(),
        "```",
        "",
    ]
    SALIDA.write_text("\n".join(lineas))


if __name__ == "__main__":
    sys.exit(main())

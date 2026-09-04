# Evidencia de validacion contra el toolchain oficial

Toolchain utilizado: **GNU binutils (riscv64-unknown-elf-)**

Resultado: **36/36 casos coinciden**.

Cada caso se ensamblo con el toolchain oficial para rv32, se obtuvo
su codificacion de referencia con `objdump -d`, y se comparo contra
la salida de `./run.sh "<instruccion>"`.

| # | Instruccion | Modelo propio | objdump -d | Coincide |
|---|---|---|---|---|
| 1 | `add x5, x6, x7` | `0x007302b3` | `0x007302b3` | si |
| 2 | `add x1, x0, x2` | `0x002000b3` | `0x002000b3` | si |
| 3 | `add x31, x30, x29` | `0x01df0fb3` | `0x01df0fb3` | si |
| 4 | `sub x10, x11, x12` | `0x40c58533` | `0x40c58533` | si |
| 5 | `sub x5, x5, x5` | `0x405282b3` | `0x405282b3` | si |
| 6 | `sub x31, x0, x31` | `0x41f00fb3` | `0x41f00fb3` | si |
| 7 | `and x7, x8, x9` | `0x009473b3` | `0x009473b3` | si |
| 8 | `and x0, x1, x2` | `0x0020f033` | `0x0020f033` | si |
| 9 | `and x31, x31, x0` | `0x000fffb3` | `0x000fffb3` | si |
| 10 | `or x13, x14, x15` | `0x00f766b3` | `0x00f766b3` | si |
| 11 | `or x2, x0, x3` | `0x00306133` | `0x00306133` | si |
| 12 | `or x31, x29, x30` | `0x01eeefb3` | `0x01eeefb3` | si |
| 13 | `addi x5, x6, 100` | `0x06430293` | `0x06430293` | si |
| 14 | `addi x7, x8, -100` | `0xf9c40393` | `0xf9c40393` | si |
| 15 | `addi x9, x10, 2047` | `0x7ff50493` | `0x7ff50493` | si |
| 16 | `andi x11, x12, 255` | `0x0ff67593` | `0x0ff67593` | si |
| 17 | `andi x13, x14, -256` | `0xf0077693` | `0xf0077693` | si |
| 18 | `andi x15, x16, -2048` | `0x80087793` | `0x80087793` | si |
| 19 | `lw x5, 8(x6)` | `0x00832283` | `0x00832283` | si |
| 20 | `lw x7, -8(x8)` | `0xff842383` | `0xff842383` | si |
| 21 | `lw x9, 2047(x10)` | `0x7ff52483` | `0x7ff52483` | si |
| 22 | `lb x11, 4(x12)` | `0x00460583` | `0x00460583` | si |
| 23 | `lb x13, -1(x14)` | `0xfff70683` | `0xfff70683` | si |
| 24 | `lb x15, -2048(x16)` | `0x80080783` | `0x80080783` | si |
| 25 | `sw x5, 16(x6)` | `0x00532823` | `0x00532823` | si |
| 26 | `sw x7, -16(x8)` | `0xfe742823` | `0xfe742823` | si |
| 27 | `sw x9, 2047(x10)` | `0x7e952fa3` | `0x7e952fa3` | si |
| 28 | `sb x11, 1(x12)` | `0x00b600a3` | `0x00b600a3` | si |
| 29 | `sb x13, -1(x14)` | `0xfed70fa3` | `0xfed70fa3` | si |
| 30 | `sb x15, -2048(x16)` | `0x80f80023` | `0x80f80023` | si |
| 31 | `beq x1, x2, 8` | `0x00208463` | `0x00208463` | si |
| 32 | `beq x3, x4, -8` | `0xfe418ce3` | `0xfe418ce3` | si |
| 33 | `beq x5, x6, 0` | `0x00628063` | `0x00628063` | si |
| 34 | `bne x7, x8, 16` | `0x00839863` | `0x00839863` | si |
| 35 | `bne x9, x10, -16` | `0xfea498e3` | `0xfea498e3` | si |
| 36 | `bne x11, x12, 4094` | `0x7ec59fe3` | `0x7ec59fe3` | si |

## Salida completa de `objdump -d`

```

/home/tomeito/GitProjects/codificador_instrucciones_RISCV/build/casos.o:     file format elf32-littleriscv


Disassembly of section .text:

00000000 <.text>:
   0:	007302b3          	add	t0,t1,t2
   4:	002000b3          	add	ra,zero,sp
   8:	01df0fb3          	add	t6,t5,t4
   c:	40c58533          	sub	a0,a1,a2
  10:	405282b3          	sub	t0,t0,t0
  14:	41f00fb3          	neg	t6,t6
  18:	009473b3          	and	t2,s0,s1
  1c:	0020f033          	and	zero,ra,sp
  20:	000fffb3          	and	t6,t6,zero
  24:	00f766b3          	or	a3,a4,a5
  28:	00306133          	or	sp,zero,gp
  2c:	01eeefb3          	or	t6,t4,t5
  30:	06430293          	addi	t0,t1,100
  34:	f9c40393          	addi	t2,s0,-100
  38:	7ff50493          	addi	s1,a0,2047
  3c:	0ff67593          	andi	a1,a2,255
  40:	f0077693          	andi	a3,a4,-256
  44:	80087793          	andi	a5,a6,-2048
  48:	00832283          	lw	t0,8(t1)
  4c:	ff842383          	lw	t2,-8(s0)
  50:	7ff52483          	lw	s1,2047(a0)
  54:	00460583          	lb	a1,4(a2)
  58:	fff70683          	lb	a3,-1(a4)
  5c:	80080783          	lb	a5,-2048(a6)
  60:	00532823          	sw	t0,16(t1)
  64:	fe742823          	sw	t2,-16(s0)
  68:	7e952fa3          	sw	s1,2047(a0)
  6c:	00b600a3          	sb	a1,1(a2)
  70:	fed70fa3          	sb	a3,-1(a4)
  74:	80f80023          	sb	a5,-2048(a6)
  78:	00208463          	beq	ra,sp,80 <.text+0x80>
  7c:	fe418ce3          	beq	gp,tp,74 <.text+0x74>
  80:	00628063          	beq	t0,t1,80 <.text+0x80>
  84:	00839863          	bne	t2,s0,94 <.text+0x94>
  88:	fea498e3          	bne	s1,a0,78 <.text+0x78>
  8c:	7ec59fe3          	bne	a1,a2,108a <.text+0x108a>
```

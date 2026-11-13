#!/bin/bash
V=/mnt/c/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali
L=$V/verilog_lib.v
echo "=== lib size ==="; wc -l "$L"
for m in AOI221X1 AO22X1 ISOLANDX1 SDFFX1 OA22X1 NBUFFX2 LSDNX1 XOR3X1; do
  echo "=== $m ==="
  awk "/^module $m/,/^endmodule/" "$L" | head -14
done

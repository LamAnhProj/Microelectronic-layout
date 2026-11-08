v {xschem version=3.4.4 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N 420 -400 420 -360 {lab=VDD}
N 420 -360 500 -360 {lab=VDD}
N 500 -360 500 -320 {lab=VDD}
N 420 -360 420 -350 {lab=VDD}
N 420 -320 500 -320 {lab=VDD}
N 380 -320 380 -260 {lab=IN}
N 340 -260 380 -260 {lab=IN}
N 380 -260 380 -200 {lab=IN}
N 420 -290 420 -260 {lab=OUT}
N 420 -260 420 -230 {lab=OUT}
N 420 -260 460 -260 {lab=OUT}
N 420 -170 420 -160 {lab=VSS}
N 420 -160 500 -160 {lab=VSS}
N 420 -160 420 -140 {lab=VSS}
N 420 -200 500 -200 {lab=VSS}
N 500 -200 500 -160 {lab=VSS}
C {devices/ipin.sym} 340 -260 0 0 {name=p_in lab=IN}
C {devices/opin.sym} 460 -260 0 0 {name=p_out lab=OUT}
C {devices/ipin.sym} 420 -400 0 0 {name=p_vdd lab=VDD}
C {devices/ipin.sym} 420 -140 0 0 {name=p_vss lab=VSS}
C {sky130_fd_pr/nfet_01v8.sym} 400 -200 0 0 {name=MN L=0.15 W=1 nf=1 mult=1 ad=0.29 as=0.29 pd=2.58 ps=2.58 nrd=0 nrs=0 sa=0 sb=0 sd=0 model=nfet_01v8 spiceprefix=X}
C {sky130_fd_pr/pfet_01v8.sym} 400 -320 0 0 {name=MP L=0.15 W=2 nf=1 mult=1 ad=0.58 as=0.58 pd=4.58 ps=4.58 nrd=0 nrs=0 sa=0 sb=0 sd=0 model=pfet_01v8 spiceprefix=X}
T {SKY130A CMOS inverter · editable source for the lab} 160 -70 0 0 0.3 0.3 {}

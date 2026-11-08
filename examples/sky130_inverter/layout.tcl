proc rect {layer x1 y1 x2 y2} {
    box values ${x1}um ${y1}um ${x2}um ${y2}um
    paint $layer
}
proc via {x y} {
    rect via1 [expr {$x - 0.13}] [expr {$y - 0.13}] [expr {$x + 0.13}] [expr {$y + 0.13}]
}
load inverter
box values 0um 0um 0um 0um
magic::gencell sky130::sky130_fd_pr__nfet_01v8 MN w 1 l 0.15
# Bring PMOS 1 um closer to shorten the gate and outer metal2 buses.
box values 0um 4um 0um 4um
magic::gencell sky130::sky130_fd_pr__pfet_01v8 MP w 2 l 0.15
# Enlarge metal1 contact pads to support legal via1 geometry.
foreach y {1.55 6.1} { rect metal1 0.41 [expr {$y-0.16}] 0.73 [expr {$y+0.16}] }
foreach y {0.95 5.35} { rect metal1 0.85 [expr {$y-0.16}] 1.17 [expr {$y+0.16}] }
foreach y {2.10 7.18} { rect metal1 0.63 [expr {$y-0.16}] 0.95 [expr {$y+0.16}] }
# Increase the otherwise undersized unused lower gate-contact metal1.
rect metal1 0.645 0.30 0.935 0.625
rect metal1 0.645 4.30 0.935 4.625
foreach point {{0.57 1.55} {1.01 0.95} {0.79 2.10} {0.57 6.1} {1.01 5.35} {0.79 7.18}} {via {*}$point}
# Drain bus = OUT. Keep the port-side spine close to the devices.
rect metal2 -1.36 1.39 0.73 1.71
rect metal2 -1.36 5.94 0.73 6.26
rect metal2 -1.36 1.39 -1.04 6.26
# Gate bus = IN. Maintain clearance from the VDD/VSS metal2 rails.
rect metal2 0.63 1.94 2.97 2.26
rect metal2 0.63 7.02 2.97 7.34
rect metal2 2.65 1.94 2.97 7.34
# Connect guard-ring local interconnect to source at each supply rail.
rect viali 1.495 0.8 1.665 0.97
rect viali 1.495 5.2 1.665 5.37
rect metal1 1.435 0.74 2.5 1.09
rect metal1 1.435 5.14 2.5 5.49
via 2.3 0.925
via 2.3 5.325
rect metal2 0.85 0.76 2.46 1.11
rect metal2 0.85 5.16 2.46 5.51
box values -1.36um 4um -1.04um 4.32um
label OUT c metal2
port make 1
box values 2.65um 4um 2.97um 4.32um
label IN c metal2
port make 2
box values 2.14um 0.78um 2.46um 1.10um
label VSS c metal2
port make 3
box values 2.14um 5.18um 2.46um 5.50um
label VDD c metal2
port make 4
select top cell
box values -10um -10um 15um 20um
drc style drc(full)
drc check
drc catchup
drc count total
foreach cell [cellname list children inverter] {
  pushstack $cell
  save $cell
  popstack
}
save inverter
extract all
ext2spice lvs
ext2spice -o inverter_lvs.spice
ext2spice default
ext2spice subcircuits top on
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice -o inverter_pex.spice
gds write inverter.gds
puts "GDS_FEEDBACK_COUNT=[feedback count]"
feedback save gds_feedback.txt
quit -noprompt

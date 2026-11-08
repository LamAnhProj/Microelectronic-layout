# Run only on a private copy of a previously saved, connected Magic cell.
# Magic 8.3.597+ requires flattening for detailed wire R-C extraction.
drc off
locking disable
crashbackups stop
box 0 0 0 0
load inverter
select top cell
flatten myflat
load myflat
cellname delete inverter
cellname rename myflat inverter
select top cell
extract do unique
extract do resistance
# Values are milliohms and picoseconds. Keep the small inverter nets visible.
extresist threshold 0
extresist mindelay 0
extresist minres 1
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist on
ext2spice -o inverter_rcx.spice
quit -noprompt

load inverter
box values 0um 0um 0um 0um
magic::gencell gf180mcu::nfet_03v3 MN w 1 l 0.28 topc 0 botc 0
box values 0um 8um 0um 8um
magic::gencell gf180mcu::pfet_03v3 MP w 2 l 0.28 topc 0 botc 0
select top cell
box values -10um -10um 20um 25um
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
gds write inverter.gds
puts "GDS_FEEDBACK_COUNT=[feedback count]"
quit -noprompt

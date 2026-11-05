# Recreate the Vivado project from source. The project directory is disposable
# and gitignored -- sources of truth are rtl/, sim/, constraints/ and bd/.
set proj_name genesys2_cv

set here [file dirname [file normalize [info script]]]
set root [file dirname $here]
set proj [file join $root vivado]

create_project $proj_name $proj -part xc7k325tffg900-2 -force
set_property board_part digilentinc.com:genesys2:part0:1.1 [current_project]

puts "PROJECT CREATED: $proj/$proj_name.xpr"

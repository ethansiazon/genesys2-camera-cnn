open_project -reset decoder_prj
set_top decode_work_heads
add_files decoder_work_r2.cpp -cflags "-std=c++14"
add_files -tb test_decoder_rtl.cpp -cflags "-std=c++14 -DRTL_SIM"
add_files -tb cases.bin
add_files -tb queries.txt
open_solution -reset solution1 -flow_target vivado
set_part {xc7k325tffg900-2}
create_clock -period 10 -name default
config_compile -pipeline_loops 0
csynth_design
exit

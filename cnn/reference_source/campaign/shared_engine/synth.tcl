open_project -reset shared_engine_prj
set_top cnn_engine
add_files cnn_engine.cpp -cflags "-std=c++14"
add_files -tb test_engine.cpp -cflags "-std=c++14 -DRTL_SIM"
add_files -tb coefficients.bin
add_files -tb input_0.bin
add_files -tb input_1.bin
add_files -tb input_2.bin
open_solution -reset solution1 -flow_target vivado
set_part {xc7k325tffg900-2}
create_clock -period 10 -name default
config_compile -pipeline_loops 0
csynth_design
exit

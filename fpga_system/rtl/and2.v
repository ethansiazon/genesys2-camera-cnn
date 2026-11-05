// Trivial 2-input AND, used to gate ap_start_seq_0/trigger on BOTH the
// coefficient copy and the feature copy finishing (C3 real-image
// investigation, 2026-10-29) -- a BD net can't express logic directly, and
// pulling in util_vector_logic for one gate is more machinery than this
// project's existing plain-RTL-glue style (copy_fsm.v, ap_start_seq.v) uses.
`timescale 1ns/1ps
module and2 (
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a & b;
endmodule

// 200 MHz board input. MMCM1: 200 MHz capture and exact 24 MHz camera XCLK.
// MMCM2: 200/5*31.5=1260 MHz VCO; /10=126 MHz serial; /50=25.2 MHz pixel.
// 800x525 totals give exactly 60 Hz. Monitor/cable compatibility needs board test.
`timescale 1ns / 1ps
`default_nettype none

module clk_gen (
    input  wire sysclk_p,       // AD12, 200 MHz LVDS
    input  wire sysclk_n,       // AD11
    output wire clk200,
    output wire clk24,
    output wire clk_pix,
    output wire clk_pix5x,
    output wire locked          // both MMCMs locked
);
    wire sysclk;
    IBUFDS #(.DIFF_TERM("TRUE"), .IBUF_LOW_PWR("FALSE"), .IOSTANDARD("LVDS"))
        ibuf_sys (.I(sysclk_p), .IB(sysclk_n), .O(sysclk));

    // ---------------- MMCM 1: capture + control domain ----------------
    // 200 MHz rather than the Basys 3's 100. PCLK is sampled as data here (see
    // cam_capture.v), and the oversample ratio is what that costs: 14x at
    // 14.4 MHz PCLK, against 7x on the Basys 3 where it already works. SCCB,
    // the UART and the probe all run in this same domain, so there is no clock
    // crossing anywhere between capture and control.
    // 200 MHz * 6 / 1 = 1200 MHz VCO (Kintex-7 -2 range is 600..1440)
    wire mmcm1_fb, clk200_i, clk24_i, locked1;
    MMCME2_BASE #(
        .CLKIN1_PERIOD(5.000),          // 200 MHz
        .DIVCLK_DIVIDE(1),
        .CLKFBOUT_MULT_F(6.000),        // VCO 1200 MHz
        .CLKOUT0_DIVIDE_F(6.000),       // 200.000 MHz
        .CLKOUT1_DIVIDE(50),            //  24.000 MHz
        .STARTUP_WAIT("FALSE")
    ) mmcm1 (
        .CLKIN1(sysclk), .CLKFBIN(mmcm1_fb), .CLKFBOUT(mmcm1_fb),
        .CLKOUT0(clk200_i), .CLKOUT1(clk24_i),
        .CLKOUT2(), .CLKOUT3(), .CLKOUT4(), .CLKOUT5(), .CLKOUT6(),
        .CLKOUT0B(), .CLKOUT1B(), .CLKOUT2B(), .CLKOUT3B(), .CLKFBOUTB(),
        .LOCKED(locked1), .PWRDWN(1'b0), .RST(1'b0)
    );

    // ---------------- MMCM 2: pixel domain ----------------
    // 200 MHz / 5 * 31.5 = 1260 MHz VCO
    wire mmcm2_fb, pix_i, pix5x_i, locked2;
    MMCME2_BASE #(
        .CLKIN1_PERIOD(5.000),
        .DIVCLK_DIVIDE(5),
        .CLKFBOUT_MULT_F(31.500),       // VCO 1260 MHz
        .CLKOUT0_DIVIDE_F(10.000),      // 126.000 MHz serial
        .CLKOUT1_DIVIDE(50),            // 25.200 MHz pixel
        .STARTUP_WAIT("FALSE")
    ) mmcm2 (
        .CLKIN1(sysclk), .CLKFBIN(mmcm2_fb), .CLKFBOUT(mmcm2_fb),
        .CLKOUT0(pix5x_i), .CLKOUT1(pix_i),
        .CLKOUT2(), .CLKOUT3(), .CLKOUT4(), .CLKOUT5(), .CLKOUT6(),
        .CLKOUT0B(), .CLKOUT1B(), .CLKOUT2B(), .CLKOUT3B(), .CLKFBOUTB(),
        .LOCKED(locked2), .PWRDWN(1'b0), .RST(1'b0)
    );

    BUFG bufg_200   (.I(clk200_i), .O(clk200));
    BUFG bufg_24    (.I(clk24_i),  .O(clk24));
    BUFG bufg_pix   (.I(pix_i),    .O(clk_pix));
    BUFG bufg_pix5x (.I(pix5x_i),  .O(clk_pix5x));

    assign locked = locked1 & locked2;
endmodule

`default_nettype wire

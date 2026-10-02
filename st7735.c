/* vim: set ai et ts=4 sw=4: */
#include "gpio.h"
#include "spi.h"
#include "st7735.h"
#include "malloc.h"
#include "string.h"
#include "st7735_config.h"

// based on Adafruit ST7735 library for Arduino
const uint8_t st7735_default_init_cmds[] = {
    19,                           // 19 commands in list:
    ST7735_SWRESET, ST7735_DELAY, //  1: Software reset, 0 args, w/delay
      150,                        //     150 ms delay
    ST7735_SLPOUT , ST7735_DELAY, //  2: Out of sleep mode, 0 args, w/delay
      255,                        //     500 ms delay
    ST7735_FRMCTR1, 3      ,      //  3: Frame rate ctrl - normal mode, 3 args:
      0x01, 0x2C, 0x2D,           //     Rate = fosc/(1x2+40) * (LINE+2C+2D)
    ST7735_FRMCTR2, 3      ,      //  4: Frame rate control - idle mode, 3 args:
      0x01, 0x2C, 0x2D,           //     Rate = fosc/(1x2+40) * (LINE+2C+2D)
    ST7735_FRMCTR3, 6      ,      //  5: Frame rate ctrl - partial mode, 6 args:
      0x01, 0x2C, 0x2D,           //     Dot inversion mode
      0x01, 0x2C, 0x2D,           //     Line inversion mode
    ST7735_INVCTR , 1      ,      //  6: Display inversion ctrl, 1 arg, no delay:
      0x07,                       //     Column inversion
    ST7735_PWCTR1 , 3      ,      //  7: Power control, 3 args, no delay:
      0xA2,                       //     AVDD = 5V; GVDD = 4.6V
      0x02,                       //     GVCL = -4.6V
      0x84,                       //     AUTO mode
    ST7735_PWCTR2 , 1      ,      //  8: Power control, 1 arg, no delay:
      0xC5,                       //     VGH25 = 2.4; VGSEL = -10; VGH = 3*AVDD-0.5
    ST7735_PWCTR3 , 2      ,      //  9: Power control, 2 args, no delay:
      0x0A,                       //     Opamp current small
      0x00,                       //     Boost frequency
    ST7735_PWCTR4 , 2      ,      // 10: Power control, 2 args, no delay:
      0x8A,                       //     BCLK/2, Opamp current small & Medium low
      0x2A,
    ST7735_PWCTR5 , 2      ,      // 11: Power control, 2 args, no delay:
      0x8A, 0xEE,
    ST7735_VMCTR1 , 1      ,      // 12: Power control, 1 arg, no delay:
      0x0E,                       //     VCOM = -0.775V
    ST7735_INVOFF , 0      ,      // 13: Don't invert display, no args, no delay
    ST7735_MADCTL , 1      ,      // 14: Memory access control (directions), 1 arg:
      ST7735_ROTATION,            //     row addr/col addr, bottom to top refresh
    ST7735_COLMOD , 1      ,      // 15: set color mode, 1 arg, no delay:
      0x05,                       //     16-bit color
#ifdef ST7735_INVERT_COLORS
    ST7735_INVON  , 0     ,       // 16: Invert display
#else
    ST7735_NOP    , 0     ,       // 16: No operation
#endif
    ST7735_GMCTRP1, 16      ,     // 17: Gamma Adjustments (pos. polarity), 16 args, no delay:
      0x02, 0x1c, 0x07, 0x12,
      0x37, 0x32, 0x29, 0x2d,
      0x29, 0x25, 0x2B, 0x39,
      0x00, 0x01, 0x03, 0x10,
    ST7735_GMCTRN1, 16      ,     // 18: Gamma Adjustments (neg. polarity), 16 args, no delay:
      0x03, 0x1d, 0x07, 0x06,
      0x2E, 0x2C, 0x29, 0x2D,
      0x2E, 0x2E, 0x37, 0x3F,
      0x00, 0x00, 0x02, 0x10,
    ST7735_NORON  , ST7735_DELAY, // 19: Normal display on, no args, w/delay
      10 };                       //     10 ms delay

static const uint16_t palette_grayscale16[16] = {
    ST7735_COLOR565(0, 0, 0),
    ST7735_COLOR565(17, 17, 17),
    ST7735_COLOR565(34, 34, 34),
    ST7735_COLOR565(51, 51, 51),
    ST7735_COLOR565(68, 68, 68),
    ST7735_COLOR565(85, 85, 85),
    ST7735_COLOR565(102, 102, 102),
    ST7735_COLOR565(119, 119, 119),
    ST7735_COLOR565(136, 136, 136),
    ST7735_COLOR565(153, 153, 153),
    ST7735_COLOR565(170, 170, 170),
    ST7735_COLOR565(187, 187, 187),
    ST7735_COLOR565(204, 204, 204),
    ST7735_COLOR565(221, 221, 221),
    ST7735_COLOR565(238, 238, 238),
    ST7735_COLOR565(255, 255, 255) };


static void ST7735_Select() {
    HAL_GPIO_WritePin(ST7735_CS_GPIO_Port, ST7735_CS_Pin, GPIO_PIN_RESET);
}

void ST7735_Unselect() {
    HAL_GPIO_WritePin(ST7735_CS_GPIO_Port, ST7735_CS_Pin, GPIO_PIN_SET);
}

static void ST7735_Reset() {
    HAL_GPIO_WritePin(ST7735_RES_GPIO_Port, ST7735_RES_Pin, GPIO_PIN_RESET);
    HAL_Delay(5);
    HAL_GPIO_WritePin(ST7735_RES_GPIO_Port, ST7735_RES_Pin, GPIO_PIN_SET);
}

static void ST7735_WriteCommand(uint8_t cmd) {
    HAL_GPIO_WritePin(ST7735_DC_GPIO_Port, ST7735_DC_Pin, GPIO_PIN_RESET);
    HAL_SPI_Transmit(&ST7735_SPI_PORT, &cmd, sizeof(cmd), HAL_MAX_DELAY);
}

static void ST7735_WriteData(uint8_t* buff, size_t buff_size) {
    HAL_GPIO_WritePin(ST7735_DC_GPIO_Port, ST7735_DC_Pin, GPIO_PIN_SET);
    HAL_SPI_Transmit(&ST7735_SPI_PORT, buff, buff_size, HAL_MAX_DELAY);
}

void ST7735_ExecuteCommand(uint8_t cmd, uint8_t* data, uint8_t data_size)
{
    ST7735_Select();
    ST7735_WriteCommand(cmd);

    if (data != NULL && data_size > 0) {
        ST7735_WriteData(data, data_size);
    }

    ST7735_Unselect();
}

void ST7735_ExecuteCommandList(const uint8_t *addr) {
    uint8_t numCommands, numArgs;
    uint16_t ms;

    numCommands = *addr++;
    while(numCommands--) {
        uint8_t cmd = *addr++;
        ST7735_WriteCommand(cmd);

        numArgs = *addr++;
        // If high bit set, delay follows args
        ms = numArgs & DELAY;
        numArgs &= ~DELAY;
        if(numArgs) {
            ST7735_WriteData((uint8_t*)addr, numArgs);
            addr += numArgs;
        }

        if(ms) {
            ms = *addr++;
            if(ms == 255) ms = 500;
            HAL_Delay(ms);
        }
    }
}

static void ST7735_SetAddressWindow(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1) {
    // column address set
    ST7735_WriteCommand(ST7735_CASET);
    uint8_t data[] = { 0x00, x0 + ST7735_XSTART, 0x00, x1 + ST7735_XSTART };
    ST7735_WriteData(data, sizeof(data));

    // row address set
    ST7735_WriteCommand(ST7735_RASET);
    data[1] = y0 + ST7735_YSTART;
    data[3] = y1 + ST7735_YSTART;
    ST7735_WriteData(data, sizeof(data));

    // write to RAM
    ST7735_WriteCommand(ST7735_RAMWR);
}

void ST7735_Init() {
    ST7735_Select();
    ST7735_Reset();
    HAL_Delay(130); // Up to 120 ms required per ST7735 datasheet
    ST7735_ExecuteCommandList(ST7735_INIT_CMDS);
    ST7735_Unselect();
}

void ST7735_EnableDisplay(bool enable)
{
    ST7735_Select();
    ST7735_WriteCommand(enable ? ST7735_DISPON : ST7735_DISPOFF);
    ST7735_Unselect();
}

void ST7735_DrawPixel(uint16_t x, uint16_t y, uint16_t color) {
    if((x >= ST7735_WIDTH) || (y >= ST7735_HEIGHT))
        return;

    ST7735_Select();

    ST7735_SetAddressWindow(x, y, x, y);
    uint8_t data[] = { color >> 8, color & 0xFF };
    ST7735_WriteData(data, sizeof(data));

    ST7735_Unselect();
}

static void ST7735_WriteChar(uint16_t x, uint16_t y, uint16_t height, char ch, FontDef font, uint16_t color, uint16_t bgcolor)
{
    uint32_t i, b, j;

    if (x >= ST7735_WIDTH || y >= ST7735_HEIGHT || height == 0) {
        return;
    }

    if (height > font.height) {
        height = font.height;
    }

    uint16_t width = font.width;
    if (x + width > ST7735_WIDTH) {
        width = ST7735_WIDTH - x;
    }

    if (y + height > ST7735_HEIGHT) {
        height = ST7735_HEIGHT - y;
    }

    ST7735_SetAddressWindow(x, y, x+width-1, y+height-1);

	// Replace non-printable characters with a placeholder
    if (ch < ' ' || ch > '~') {
        ch = '?';
	}

    for(i = 0; i < height; i++) {
        b = font.data[(ch - 32) * font.height + i];
        for(j = 0; j < width; j++) {
            uint8_t data[] = {
                ((b << j) & 0x8000) ? (color >> 8) : (bgcolor >> 8),
                ((b << j) & 0x8000) ? (color & 0xFF) : (bgcolor & 0xFF)
            };

            ST7735_WriteData(data, sizeof(data));
        }
    }
}

void ST7735_WriteString(uint16_t x, uint16_t y, const char* str, FontDef font, uint16_t color, uint16_t bgcolor) {
    ST7735_Select();

    while(*str) {
        if(x + font.width > ST7735_WIDTH) {
            x = 0;
            y += font.height;
            if(y >= ST7735_HEIGHT) {
                break;
            }

            if(*str == ' ') {
                // skip spaces in the beginning of the new line
                str++;
                continue;
            }
        }

        ST7735_WriteChar(x, y, font.height, *str, font, color, bgcolor);
        x += font.width;
        str++;
    }

    ST7735_Unselect();
}

void ST7735_WriteStringNoWrap(uint16_t x, uint16_t y, uint16_t max_height, const char* str, FontDef font, uint16_t color, uint16_t bgcolor)
{
    if (x >= ST7735_WIDTH || y >= ST7735_HEIGHT || max_height == 0) {
        return;
    }

    ST7735_Select();

    uint16_t height = font.height;
    if (height > max_height) {
        height = max_height;
    }

    while(*str) {
        if(x >= ST7735_WIDTH) {
            break;
        }

        ST7735_WriteChar(x, y, height, *str, font, color, bgcolor);
        x += font.width;
        str++;
    }

    ST7735_Unselect();
}

void ST7735_FillRectangle(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
    // clipping
    if((x >= ST7735_WIDTH) || (y >= ST7735_HEIGHT)) return;
    if((x + w - 1) >= ST7735_WIDTH) w = ST7735_WIDTH - x;
    if((y + h - 1) >= ST7735_HEIGHT) h = ST7735_HEIGHT - y;

    ST7735_Select();
    ST7735_SetAddressWindow(x, y, x+w-1, y+h-1);

    uint8_t data[] = { color >> 8, color & 0xFF };
    HAL_GPIO_WritePin(ST7735_DC_GPIO_Port, ST7735_DC_Pin, GPIO_PIN_SET);
    for(y = h; y > 0; y--) {
        for(x = w; x > 0; x--) {
            HAL_SPI_Transmit(&ST7735_SPI_PORT, data, sizeof(data), HAL_MAX_DELAY);
        }
    }

    ST7735_Unselect();
}

void ST7735_FillRectangleFast(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
    // clipping
    if((x >= ST7735_WIDTH) || (y >= ST7735_HEIGHT)) return;
    if((x + w - 1) >= ST7735_WIDTH) w = ST7735_WIDTH - x;
    if((y + h - 1) >= ST7735_HEIGHT) h = ST7735_HEIGHT - y;

    ST7735_Select();
    ST7735_SetAddressWindow(x, y, x+w-1, y+h-1);

    // Prepare whole line in a single buffer
    uint8_t pixel[] = { color >> 8, color & 0xFF };
    uint8_t *line = malloc(w * sizeof(pixel));
    for(x = 0; x < w; ++x)
    	memcpy(line + x * sizeof(pixel), pixel, sizeof(pixel));

    HAL_GPIO_WritePin(ST7735_DC_GPIO_Port, ST7735_DC_Pin, GPIO_PIN_SET);
    for(y = h; y > 0; y--)
        HAL_SPI_Transmit(&ST7735_SPI_PORT, line, w * sizeof(pixel), HAL_MAX_DELAY);

    free(line);
    ST7735_Unselect();
}

void ST7735_FillScreen(uint16_t color) {
    ST7735_FillRectangle(0, 0, ST7735_WIDTH, ST7735_HEIGHT, color);
}

void ST7735_FillScreenFast(uint16_t color) {
    ST7735_FillRectangleFast(0, 0, ST7735_WIDTH, ST7735_HEIGHT, color);
}

void ST7735_DrawImage(uint16_t x, uint16_t y, uint16_t w, uint16_t h, const uint16_t* data) {
    ST7735_DrawCompressedImage(x, y, w, h, ImageFormat_Raw16, (const uint8_t*)data, sizeof(uint16_t) * w * h);
}

void ST7735_DrawCompressedImage(uint16_t x, uint16_t y, uint16_t w, uint16_t h, ImageFormat format, const uint8_t* data, size_t data_size) {
    if((x >= ST7735_WIDTH) || (y >= ST7735_HEIGHT)) return;
    if((x + w - 1) >= ST7735_WIDTH) return;
    if((y + h - 1) >= ST7735_HEIGHT) return;

    ST7735_Select();
    ST7735_SetAddressWindow(x, y, x+w-1, y+h-1);

    if (format == ImageFormat_Raw16) {
        ST7735_WriteData((uint8_t*)data, data_size);
    } else if (format == ImageFormat_Grayscale4Rle4) {
        const size_t buf_size = 32;
        uint16_t     buf[buf_size];
        size_t       buf_pos = 0;

        for (size_t i = 0; i < data_size; ++i) {
            uint16_t color = palette_grayscale16[data[i] & 0x0F];
            size_t count = (data[i] >> 4) + 1;

            while (count--) {
                buf[buf_pos++] = color;

                if (buf_pos >= buf_size) {
                    ST7735_WriteData((uint8_t*)buf, sizeof(buf));
                    buf_pos = 0;
                }
            }
        }

        if (buf_pos > 0) {
            ST7735_WriteData((uint8_t*)buf, buf_pos * sizeof(buf[0]));
        }
    }

    ST7735_Unselect();
}

void ST7735_InvertColors(bool invert) {
    ST7735_Select();
    ST7735_WriteCommand(invert ? ST7735_INVON : ST7735_INVOFF);
    ST7735_Unselect();
}

void ST7735_SetGamma(GammaDef gamma)
{
	ST7735_Select();
	ST7735_WriteCommand(ST7735_GAMSET);
	ST7735_WriteData((uint8_t *) &gamma, sizeof(gamma));
	ST7735_Unselect();
}

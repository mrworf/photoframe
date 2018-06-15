/**
 *
 * Simple tool to convert between RGB888 and RGB565
 *
 * Copyright 2018 Henric Andersson (henric@sensenet.nu)
 *
 * This file is part of Photoframe.
 *
 * Photoframe is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * Photoframe is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with Photoframe.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

#define RGB888toRGB565(r,g,b) ((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3))
#define RGB565toR8(x) ((((x) >> 11) & 0x1F) * 255 / 31)
#define RGB565toG8(x) ((((x) >>  5) & 0x3F) * 255 / 63)
#define RGB565toB8(x) ((((x)      ) & 0x1F) * 255 / 31)

#define RGB888_BUFSIZE (3*1024)
#define RGB565_BUFSIZE (2*1024)

void convert565to888(void) {
    unsigned short* in_buffer = (unsigned short*)malloc(RGB565_BUFSIZE);
    unsigned char* out_buffer = (unsigned char*)malloc(RGB888_BUFSIZE);
    int i = 0;
    int size = 0;
    int remain = 0;
    char buf[256];

    while (1) {
        size = read(0, in_buffer + remain, RGB565_BUFSIZE - remain);
        if (size < 1 && remain == 0)
            break;
        size += remain;
        remain = size - (size/2)*2;
        for (i = 0; i < size/2; ++i) {
            out_buffer[i*3+0] = RGB565toR8(in_buffer[i]);
            out_buffer[i*3+1] = RGB565toG8(in_buffer[i]);
            out_buffer[i*3+2] = RGB565toB8(in_buffer[i]);
        }
        write(1, out_buffer, (size/2)*3);
        if (remain)
            memcpy(in_buffer, in_buffer+(size-remain), remain);
    }
    free(in_buffer);
    free(out_buffer);
}

void convert888to565(void) {
    unsigned char* in_buffer = (unsigned char*)malloc(RGB888_BUFSIZE);
    unsigned short* out_buffer = (unsigned short*)malloc(RGB565_BUFSIZE);
    int i = 0;
    int size = 0;
    int remain = 0;
    char buf[256];

    while (1) {
        size = read(0, in_buffer + remain, RGB888_BUFSIZE - remain);
        if (size < 1 && remain == 0)
            break;
        size += remain;
        remain = size - (size/3)*3;
        for (i = 0; i < size/3; ++i)
            out_buffer[i] = RGB888toRGB565(in_buffer[i*3], in_buffer[i*3+1], in_buffer[i*3+2]);

        write(1, out_buffer, (size/3)*2);
        if (remain)
            memcpy(in_buffer, in_buffer+(size-remain), remain);
    }
    free(in_buffer);
    free(out_buffer);
}

int main(int argc, char **argv)
{
    if (argc == 2) // Any argument will kick it into reverse
        convert565to888();
    else
        convert888to565();
    return 0;
}

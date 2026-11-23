#ifndef __COORD_RECEIVER_H
#define __COORD_RECEIVER_H

#include "ti_msp_dl_config.h"

/**********************************************************
*** UART1 坐标接收模块
*** 数据帧格式：AA 55 X_High X_Low Checksum 55 FF（共 7 字节）
*** Checksum = X_High + X_Low（仅坐标两字节求和，舍弃进位）
*** 接线：PA8(TX) 接上位机 RXD，PA9(RX) 接上位机 TXD，GND 共地
**********************************************************/

// 最近一次成功解析的坐标值（高 8 位 + 低 8 位合成 16 位）
extern __IO uint16_t g_coordX;
// 帧接收成功标志，用户读取 g_coordX 后手动清零
extern __IO bool    g_coordNew;

// 初始化 UART1 接收中断
void Coord_Init(void);
// UART1 中断服务函数（由 ti_msp_dl_config.h 的 UART_1_INST_IRQHandler 宏映射）
void UART_1_INST_IRQHandler(void);

#endif

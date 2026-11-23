#include "coord_receiver.h"

/**********************************************************
*** UART1 坐标接收模块
*** 数据帧：AA 55 X_High X_Low Checksum 55 FF（7 字节）
*** 解析状态机，逐字节匹配，任一状态校验失败则回到起始态
**********************************************************/

// 全局变量：最近一次成功解析的坐标与更新标志
__IO uint16_t g_coordX   = 0;
__IO bool     g_coordNew = false;

// 帧解析状态机
typedef enum {
    SYNC_AA   = 0,  // 等待帧头 AA
    SYNC_55   = 1,  // 等待帧头 55
    GET_XH    = 2,  // 读取 X 坐标高字节
    GET_XL    = 3,  // 读取 X 坐标低字节
    GET_CK    = 4,  // 读取校验和并比对
    SYNC_55_2 = 5,  // 等待帧中 55
    SYNC_FF   = 6,  // 等待帧尾 FF
} FrameState_t;

static FrameState_t s_state = SYNC_AA;
static uint8_t      s_xh   = 0;  // 暂存 X 高字节
static uint8_t      s_xl   = 0;  // 暂存 X 低字节

/**
 * @brief   UART1 中断服务函数
 * @note    由 UART_1_INST_IRQHandler 宏展开为 UART1_IRQHandler
 */
void UART_1_INST_IRQHandler(void)
{
    uint8_t  byte;
    uint8_t  ck;
    uint16_t x;

    if (DL_UART_getPendingInterrupt(UART_1_INST) == DL_UART_IIDX_RX)
    {
        byte = (uint8_t)DL_UART_Main_receiveData(UART_1_INST);

        switch (s_state)
        {
        /**************************************************
        *** 状态 0：等待 AA
        **************************************************/
        case SYNC_AA:
            if (byte == 0xAA) { s_state = SYNC_55; }
            break;

        /**************************************************
        *** 状态 1：等待 55（AA 的后半部）
        *** 若又收到 AA，保持在本状态（容忍 AA AA 55 场景）
        **************************************************/
        case SYNC_55:
            if (byte == 0x55)      { s_state = GET_XH; }
            else if (byte == 0xAA) { /* 仍留在 SYNC_55 */ }
            else                   { s_state = SYNC_AA; }
            break;

        /**************************************************
        *** 状态 2：读取 X 高字节
        **************************************************/
        case GET_XH:
            s_xh    = byte;
            s_state = GET_XL;
            break;

        /**************************************************
        *** 状态 3：读取 X 低字节
        **************************************************/
        case GET_XL:
            s_xl    = byte;
            s_state = GET_CK;
            break;

        /**************************************************
        *** 状态 4：校验 checksum
        *** ck == (XH + XL) 低 8 位则通过，否则回起始态
        **************************************************/
        case GET_CK:
            ck = s_xh + s_xl;
            if (byte == ck) { s_state = SYNC_55_2; }
            else            { s_state = SYNC_AA; }
            break;

        /**************************************************
        *** 状态 5：等待 55（FF 前的定界符）
        **************************************************/
        case SYNC_55_2:
            if (byte == 0x55)      { s_state = SYNC_FF; }
            else if (byte == 0xAA) { s_state = SYNC_55; }
            else                   { s_state = SYNC_AA; }
            break;

        /**************************************************
        *** 状态 6：等待 FF（帧尾）
        *** 收到 FF 则一帧完成，更新全局坐标并置标志
        **************************************************/
        case SYNC_FF:
            if (byte == 0xFF)
            {
                x           = ((uint16_t)s_xh << 8) | (uint16_t)s_xl;
                g_coordX    = x;
                g_coordNew  = true;
            }
            // 不论 FF 是否匹配都回到起始态，重新同步
            s_state = SYNC_AA;
            break;

        default:
            s_state = SYNC_AA;
            break;
        }
    }

    DL_UART_clearInterruptStatus(UART_1_INST, DL_UART_IIDX_RX);
}

/**
 * @brief   初始化 UART1 接收：清中断标志并使能 NVIC
 */
void Coord_Init(void)
{
    s_state   = SYNC_AA;
    g_coordNew = false;
    g_coordX   = 0;

    NVIC_ClearPendingIRQ(UART_1_INST_INT_IRQN);
    NVIC_EnableIRQ(UART_1_INST_INT_IRQN);
}

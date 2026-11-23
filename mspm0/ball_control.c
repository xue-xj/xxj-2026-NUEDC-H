/*
 * Copyright (c) 2021, Texas Instruments Incorporated
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "ball_control.h"
#include "app_settings.h"
#include "coord_receiver.h"

/* 本模块保留原状态机及调用顺序；小车阶段是本地时序，非实测加速度。 */
typedef enum {
    FUNC_BALL_TARGETS = 0,   // 功能一：小球在 325 和 565 之间移动
    FUNC_CART_BALANCE = 1,   // 功能二：小车运动 + 小球 PID 平衡在 400
} FuncMode_t;

// ---- 功能一：阶段枚举 ----
typedef enum {
    STAGE_GO_325 = 0,        // 正在去 325
    STAGE_GO_565 = 1,        // 正在去 565
    STAGE_DONE   = 2,        // 全部完成，维持最后目标
} Stage_t;

// ---- 功能二：小车运动状态 ----
typedef enum {
    CART_ACCEL   = 0,        // 起步加速
    CART_CRUISE  = 1,        // 匀速运动
    CART_DECEL   = 2,        // 减速刹车
    CART_STOPPED = 3,        // 已停止，进入阻尼镇定
} CartState_t;

/**********************************************************
***  全局变量（Watch 窗口可观察）
**********************************************************/
Gimbal_Telemetry_t g_tm = {0};    // 云台遥测
PID_t              g_pid;          // PID 控制器
float              g_pidOutput;    // PID 计算输出的角度
float              g_ballPos;      // 小球当前坐标（串口原始坐标，本模块未滤波）
float              g_ballError;    // 坐标误差（目标 - 实际）

/**********************************************************
***  模块级静态变量
**********************************************************/

// ---- 按键状态 ----
static bool     s_btnPressed   = false;   // 消抖后的按键状态（true=按下）
static uint8_t  s_btnCnt       = 0;       // 消抖计数
static bool     s_btnRawPrev    = false;   // 上一次原始读数

// ---- 当前功能模式（默认功能一）----
static FuncMode_t s_funcMode   = FUNC_BALL_TARGETS;

// ---- 功能一状态 ----
static Stage_t  s_stage        = STAGE_GO_325;
static uint8_t  s_dwellCount   = 0;

// ---- 功能二状态 ----
static CartState_t s_cartState = CART_ACCEL;
static uint32_t    s_cartTimer = 0;       // 当前阶段已持续的循环次数
static float       s_ballPrev  = 0.0f;    // 上一周期小球位置（计算速度用）
static float       s_ballVel   = 0.0f;    // 小球移动速度（坐标/秒）
static uint8_t     s_settleCnt = 0;       // 连续稳定计数

/**********************************************************
***  内部辅助函数声明
**********************************************************/
static void SwitchFunction(void);
static void PollButton(void);
static void Func2_UpdateCartState(void);
static float Func2_ComputeAngle(float ballPos);
static void Func2_Reset(void);
static void Func1_Reset(void);

/**********************************************************
***  功能切换
**********************************************************/
/**
 * @brief   在定点平衡与小车补偿两种模式之间切换
 */
static void SwitchFunction(void)
{
    Gimbal_Stop();

    if (s_funcMode == FUNC_BALL_TARGETS)
    {
        s_funcMode = FUNC_CART_BALANCE;
        Func2_Reset();
    }
    else
    {
        s_funcMode = FUNC_BALL_TARGETS;
        Func1_Reset();
    }
}

/**
 * @brief   重置功能一的状态
 */
static void Func1_Reset(void)
{
    PID_Init(&g_pid, PID_KP, PID_KI, PID_KD,
             PID_DT, -ANGLE_LIMIT, ANGLE_LIMIT);
    PID_SetSetpoint(&g_pid, TARGET_0);

    s_stage      = STAGE_GO_325;
    s_dwellCount = 0;
}

/**
 * @brief   重置功能二的状态
 */
static void Func2_Reset(void)
{
    PID_Init(&g_pid, F2_PID_KP, F2_PID_KI, F2_PID_KD,
             F2_PID_DT, -F2_ANGLE_LIMIT, F2_ANGLE_LIMIT);
    PID_SetSetpoint(&g_pid, F2_TARGET);

    s_cartState  = CART_ACCEL;
    s_cartTimer  = 0;
    s_ballPrev   = g_ballPos;
    s_ballVel    = 0.0f;
    s_settleCnt  = 0;
}

/**********************************************************
***  按键轮询（内部上拉 → GND，按下为低电平）
**********************************************************/
/**
 * @brief   通用按键消抖 + 边沿检测
 * @note    PB6 低电平按下；稳定按下后只切换一次模式。
 */
static void PollButton(void)
{
    bool btn_raw = (DL_GPIO_readPins(BUTTON_PB6_PORT,
                                     BUTTON_PB6_PIN_0_PIN) == 0);

    if (btn_raw == s_btnRawPrev)
    {
        if (s_btnCnt < 255) { s_btnCnt++; }
    }
    else
    {
        s_btnCnt     = 0;
        s_btnRawPrev = btn_raw;
    }

    if (s_btnCnt >= BTN_DEBOUNCE && btn_raw != s_btnPressed)
    {
        s_btnPressed = btn_raw;
        s_btnCnt     = 0;

        if (s_btnPressed)
        {
            SwitchFunction();
        }
    }
}

/**********************************************************
***  功能二：更新小车运动状态
**********************************************************/
/**
 * @brief   根据累积时间切换小车运动阶段
 * @note    每主循环调用一次；阶段时间按循环次数估算，包含通信耗时误差
 *          CART_STOPPED 阶段由小球稳定条件自动退出
 */
static void Func2_UpdateCartState(void)
{
    uint32_t elapsed_ms = s_cartTimer * LOOP_DELAY_MS;

    switch (s_cartState)
    {
    case CART_ACCEL:
        if (elapsed_ms >= CART_ACCEL_MS)
        {
            s_cartState = CART_CRUISE;
            s_cartTimer = 0;
        }
        break;

    case CART_CRUISE:
        if (elapsed_ms >= CART_CRUISE_MS)
        {
            s_cartState = CART_DECEL;
            s_cartTimer = 0;
        }
        break;

    case CART_DECEL:
        if (elapsed_ms >= CART_DECEL_MS)
        {
            s_cartState = CART_STOPPED;
            s_cartTimer = 0;
            s_settleCnt = 0;
        }
        break;

    case CART_STOPPED:
        /* 小球稳定（速度小 + 位置误差小）后重新开始运动循环 */
        if (ABS(s_ballVel) < F2_SETTLE_VEL &&
            ABS(g_ballPos - F2_TARGET) < F2_SETTLE_ERR)
        {
            if (++s_settleCnt >= F2_SETTLE_CNT)
            {
                /* 小球已稳定，开始下一轮运动 */
                s_cartState = CART_ACCEL;
                s_cartTimer = 0;
                s_settleCnt = 0;
                PID_Reset(&g_pid);
            }
        }
        else
        {
            s_settleCnt = 0;
        }
        break;
    }
}

/**********************************************************
***  功能二：计算电机角度
**********************************************************/
/**
 * @brief   综合前馈补偿 + PID 反馈 + 阻尼，计算最终电机角度
 * @param   ballPos   小球当前坐标
 * @retval  电机目标角度（度）
 * @note
 *   - ACCEL 阶段：前馈负角度，抵消小球向后（滞后）的惯性
 *   - CRUISE 阶段：仅 PID 维持目标
 *   - DECEL 阶段：前馈正角度，抵消小球向前（冲量）的惯性
 *   - STOPPED 阶段：PID + 阻尼（方向与小球速度相反）
 */
static float Func2_ComputeAngle(float ballPos)
{
    float ff_angle = 0.0f;    // 前馈 / 阻尼角度
    float pid_out;

    switch (s_cartState)
    {
    case CART_ACCEL:
        /* 小车加速 → 小球因惯性滞后 → 水管后倾补偿（负角度）*/
        ff_angle = -F2_FF_GAIN;
        break;

    case CART_CRUISE:
        /* 匀速阶段无惯性力，仅 PID 即可 */
        ff_angle = 0.0f;
        break;

    case CART_DECEL:
        /* 小车减速 → 小球因惯性前冲 → 水管前倾补偿（正角度）*/
        ff_angle = F2_FF_GAIN;
        break;

    case CART_STOPPED:
        /* 阻尼：电机角度与小球运动方向相反，快速消除摆动 */
        ff_angle = -F2_DAMP_GAIN * s_ballVel;
        break;
    }

    /* PID 反馈（维持目标坐标）+ 前馈/阻尼 */
    pid_out = PID_Compute(&g_pid, ballPos);

    return pid_out + ff_angle;
}


void BallControl_Init(void)
{
    Func1_Reset();

/**********************************************************
***  上电后先刷一次遥测确认通信正常
**********************************************************/
    Gimbal_UpdateTelemetry(&g_tm);
    g_ballPos   = (float)g_coordX;
    g_ballError = 0.0f;

}

void BallControl_Update(void)
{
    /* -------- 按键轮询（消抖 + 功能切换）-------- */
    PollButton();

    /* -------- 有新坐标到达时参与控制 -------- */
    if (g_coordNew)
    {
        g_ballPos = (float)g_coordX;
        g_coordNew = false;

        /* 根据当前功能选择安全范围 */
        float safeMin, safeMax;
        if (s_funcMode == FUNC_BALL_TARGETS)
        {
            safeMin = COORD_SAFE_MIN;
            safeMax = COORD_SAFE_MAX;
        }
        else
        {
            safeMin = F2_COORD_MIN;
            safeMax = F2_COORD_MAX;
        }

        /* 超出安全范围则停止电机，等待数据恢复 */
        if (g_ballPos < safeMin || g_ballPos > safeMax)
        {
            Gimbal_Stop();
            PID_Reset(&g_pid);
        }
        else
        {
            if (s_funcMode == FUNC_BALL_TARGETS)
            {
                /**************************************************
                ***  功能一：小球在两个目标坐标间移动
                **************************************************/

                /* ---- 阶段切换逻辑 ---- */
                if (s_stage == STAGE_GO_325)
                {
                    if (ABS(g_ballPos - TARGET_0) <= ARRIVE_TOL_0)
                    {
                        if (++s_dwellCount >= DWELL_CNT)
                        {
                            s_stage      = STAGE_GO_565;
                            s_dwellCount = 0;
                            PID_SetSetpoint(&g_pid, TARGET_1);
                            PID_Reset(&g_pid);
                        }
                    }
                    else
                    {
                        s_dwellCount = 0;
                    }
                }
                else if (s_stage == STAGE_GO_565)
                {
                    if (ABS(g_ballPos - TARGET_1) <= ARRIVE_TOL_1)
                    {
                        if (++s_dwellCount >= DWELL_CNT)
                        {
                            s_stage = STAGE_DONE;
                        }
                    }
                    else
                    {
                        s_dwellCount = 0;
                    }
                }
                /* STAGE_DONE：不做切换，维持最后一个目标 */

                /* ---- PID 计算 ---- */
                g_pidOutput = PID_Compute(&g_pid, g_ballPos);
                g_ballError = g_pid.setpoint - g_ballPos;
            }
            else  /* s_funcMode == FUNC_CART_BALANCE */
            {
                /**************************************************
                ***  功能二：小车运动 + PID 小球平衡
                **************************************************/

                /* ---- 计算小球速度（坐标/秒）---- */
                s_ballVel = (g_ballPos - s_ballPrev) / F2_PID_DT;
                s_ballPrev = g_ballPos;

                /* ---- 综合前馈 + PID + 阻尼 ---- */
                g_pidOutput = Func2_ComputeAngle(g_ballPos);
                g_ballError = g_pid.setpoint - g_ballPos;
            }

            /* 下发云台角度；原驱动会等待应答，此处并非严格非阻塞 */
            Gimbal_MoveTo(g_pidOutput);
        }
    }

    /* -------- 功能二：更新小车运动阶段（独立于坐标更新）-------- */
    if (s_funcMode == FUNC_CART_BALANCE)
    {
        s_cartTimer++;
        Func2_UpdateCartState();
    }

    /* -------- 持续刷新遥测 -------- */
    Gimbal_UpdateTelemetry(&g_tm);
}

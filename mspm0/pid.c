#include "pid.h"

/**********************************************************
***  PID 控制器实现
***  公式：output = Kp*e + Ki*∫e·dt + Kd*de/dt
***  积分抗饱和（clamping）：输出饱和时停止积分累加
**********************************************************/

/**
 * @brief   初始化 PID
 * @param   pid     PID 结构体指针
 * @param   kp, ki, kd   PID 三参数
 * @param   dt      采样周期（秒），与主循环周期一致
 * @param   outMin  输出下限
 * @param   outMax  输出上限
 */
void PID_Init(PID_t *pid, float kp, float ki, float kd,
              float dt, float outMin, float outMax)
{
    pid->Kp        = kp;
    pid->Ki        = ki;
    pid->Kd        = kd;
    pid->dt        = dt;
    pid->outMin    = outMin;
    pid->outMax    = outMax;
    pid->setpoint  = 0.0f;
    pid->integral  = 0.0f;
    pid->prevError = 0.0f;
    pid->first     = true;
}

/**
 * @brief   更新目标设定值
 */
void PID_SetSetpoint(PID_t *pid, float sp)
{
    pid->setpoint = sp;
}

/**
 * @brief   清除历史状态（切换目标或模式时调用）
 */
void PID_Reset(PID_t *pid)
{
    pid->integral  = 0.0f;
    pid->prevError = 0.0f;
    pid->first     = true;
}

/**
 * @brief   PID 核心计算
 * @param   pid          PID 结构体
 * @param   measurement  当前测量值（小球实际坐标）
 * @retval  控制输出（云台角度）
 * @note    error = setpoint - measurement（标准定义）
 *          输出符号已处理：error>0 时输出负值，对应电机反转
 */
float PID_Compute(PID_t *pid, float measurement)
{
    float error, pTerm, iTerm, dTerm, output;

    // ---- 计算误差（标准：设定值 - 测量值）----
    error = pid->setpoint - measurement;

    // ---- 比例项 ----
    pTerm = pid->Kp * error;

    // ---- 积分项（梯形近似，抗饱和 clamping）----
    if (!pid->first)
    {
        pid->integral += pid->Ki * error * pid->dt;
    }

    // ---- 微分项（误差微分，首次跳过）----
    if (!pid->first)
    {
        dTerm = pid->Kd * (error - pid->prevError) / pid->dt;
    }
    else
    {
        dTerm = 0.0f;
        pid->first = false;
    }

    // ---- 合成输出 ----
    output = pTerm + pid->integral + dTerm;

    // ---- 输出限幅 + 积分抗饱和 ----
    if (output > pid->outMax)
    {
        output = pid->outMax;
        // 饱和时回退本次积分累加（clamping）
        if (pid->Ki != 0.0f && error > 0.0f)
        {
            pid->integral -= pid->Ki * error * pid->dt;
        }
    }
    else if (output < pid->outMin)
    {
        output = pid->outMin;
        if (pid->Ki != 0.0f && error < 0.0f)
        {
            pid->integral -= pid->Ki * error * pid->dt;
        }
    }

    // ---- 保存误差供下次微分 ----
    pid->prevError = error;

    return output;
}

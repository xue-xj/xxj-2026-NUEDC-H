#ifndef __PID_H
#define __PID_H

#include <stdbool.h>

/**********************************************************
***  PID 控制器模块
***  标准位置式 PID，带积分抗饱和（clamping）
***  用法：
***    1. PID_Init(&pid, kp, ki, kd, dt, outMin, outMax)
***    2. PID_SetSetpoint(&pid, target)
***    3. 循环调用 output = PID_Compute(&pid, measurement)
***       output 即为控制量（本项目中为云台角度°）
**********************************************************/

typedef struct {
    float Kp;           // 比例系数
    float Ki;           // 积分系数
    float Kd;           // 微分系数
    float dt;           // 采样周期（秒），用于积分/微分时间归一化
    float setpoint;     // 目标设定值
    float integral;     // 积分累加项
    float prevError;    // 上一次误差（微分用）
    float outMin;       // 输出下限
    float outMax;       // 输出上限
    bool  first;        // 首次计算标志
} PID_t;

// 初始化 PID 结构体
void  PID_Init(PID_t *pid, float kp, float ki, float kd,
               float dt, float outMin, float outMax);
// 设定目标值（可在运行中随时修改）
void  PID_SetSetpoint(PID_t *pid, float sp);
// 给定当前测量值，返回 PID 计算输出的控制量
float PID_Compute(PID_t *pid, float measurement);
// 清除积分累加和微分记忆（切换目标时调用）
void  PID_Reset(PID_t *pid);

#endif

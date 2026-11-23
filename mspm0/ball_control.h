#ifndef BALL_CONTROL_H
#define BALL_CONTROL_H
#include "gimbal.h"
#include "pid.h"

/* 保留 Watch 窗口符号，方便现场观察控制状态。 */
extern Gimbal_Telemetry_t g_tm;
extern PID_t g_pid;
extern float g_pidOutput, g_ballPos, g_ballError;

/* 外设、坐标接收与电机初始化后调用一次。 */
void BallControl_Init(void);
/* 每轮主循环调用；内部仅在收到新坐标时更新 PID。 */
void BallControl_Update(void);
#endif

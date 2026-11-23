#ifndef APP_SETTINGS_H
#define APP_SETTINGS_H

/* 集中调参；数值保留原工程，重构不改变控制行为。 */
#define PID_KP          0.12f       // 比例系数（坐标范围 0-800）
#define PID_KI          0.06f       // 积分系数
#define PID_KD          0.03f       // 微分系数

// ---- PID 采样周期（秒），应与主循环周期一致 ----
#define PID_DT          0.015f      // 算法使用的标称 dt；实际周期还包含串口等待，不是定时中断周期

// ---- 云台角度输出限幅 ----
#define ANGLE_LIMIT     15.0f

// ---- 小球坐标安全范围（超出视为传感器异常，停止控制）----
#define COORD_SAFE_MIN  0.0f
#define COORD_SAFE_MAX  800.0f

// ---- 目标切换参数 ----
#define TARGET_0        325.0f      // 第一个目标坐标
#define TARGET_1        565.0f      // 第二个目标坐标
#define ARRIVE_TOL_0    15.0f       // 第一个目标到位容差 ±15
#define ARRIVE_TOL_1    30.0f       // 第二个目标到位容差 ±30
#define DWELL_CNT       6           // 连续在容差内多少次才确认到达（按收到的新坐标计数，不按真实时间）

/**********************************************************
***  功能二：小车运动 + 水管小球 PID 平衡 — 调参区
**********************************************************/

// ---- PID 参数（功能二使用独立的 PID 参数）----
#define F2_PID_KP       0.08f       // 比例系数
#define F2_PID_KI       0.03f       // 积分系数
#define F2_PID_KD       0.04f       // 微分系数
#define F2_PID_DT       0.015f      // 采样周期（秒）

// ---- 角度输出限幅 ----
#define F2_ANGLE_LIMIT  20.0f

// ---- 目标坐标（功能二恒定维持在 400）----
#define F2_TARGET       400.0f

// ---- 坐标安全范围 ----
#define F2_COORD_MIN    0.0f
#define F2_COORD_MAX    800.0f

// ---- 前馈补偿增益（抵消小车加减速时小球的惯性）----
#define F2_FF_GAIN      5.0f        // 加速/减速时施加的前馈角度（度）

// ---- 阻尼增益（小车停止时，电机施加与小球运动方向相反的力矩）----
#define F2_DAMP_GAIN    0.3f        // 阻尼系数（度 / (坐标/秒)）

// ---- 停止后小球稳定判定阈值 ----
#define F2_SETTLE_VEL   10.0f       // 速度阈值（坐标/秒），低于此值视为稳定
#define F2_SETTLE_ERR   10.0f       // 位置误差阈值（坐标），低于此值视为稳定
#define F2_SETTLE_CNT   30          // 连续稳定次数（30*10ms=300ms）后重新开始运动循环

// ---- 小车运动时序（毫秒）----
#define CART_ACCEL_MS   2000        // 起步加速阶段
#define CART_CRUISE_MS  3000        // 匀速运动阶段
#define CART_DECEL_MS   2000        // 减速刹车阶段
// CART_STOPPED 阶段不设固定时长，待小球稳定后自动进入下一循环

/**********************************************************
***  通用参数
**********************************************************/

// ---- 电机运动参数 ----
#define MOTOR_SPEED     800         // 转速 RPM，响应要快但不能失步
#define MOTOR_ACC       20          // 加速度（0-255，0 为直接启动）

// ---- 按键消抖 ----
#define BTN_DEBOUNCE    1           // 连续 1 次（10ms）采样一致才确认

// ---- 主循环延时 ----
#define LOOP_DELAY_MS   10


#endif

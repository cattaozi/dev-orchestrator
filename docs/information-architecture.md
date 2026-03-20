# 信息架构与核心流程（V1）

## 一、页面结构

1. `Dashboard`（首页）
- 今日任务概览
- 项目运行状态卡片
- 活跃 Session 列表
- 阻塞提醒

2. `Projects`（项目列表）
- 项目卡片（文件夹路径、运行状态、快捷入口）
- 进入项目详情

3. `Project Detail`（项目详情）
- 服务运行面板（高频）
- 任务列表（高频）
- 最近 Session 摘要（高频）
- 低频配置通过 `More` 收纳

4. `Session Detail`（会话详情）
- 对话输入输出
- 结构化总结（结果、变更点、下一步）

## 二、导航优先级

- 一级导航：`Dashboard / Projects / Sessions`
- 项目内二级结构：`Services / Tasks / Recent Sessions`（同页）

## 三、关键用户流程

### 流程 A：开始一天工作

1. 打开 Dashboard  
2. 查看“阻塞任务 + 运行状态”  
3. 进入项目详情  
4. 启动所需服务  
5. 打开任务并发起 Session

### 流程 B：推进任务

1. 在任务中提出目标  
2. 发起 Session 执行  
3. 查看 Session 总结  
4. 更新任务状态（doing/done/blocked）

### 流程 C：收工

1. 查看今日完成数  
2. 标注未完成任务的下一步  
3. 停止不需要的项目服务

## 四、显示策略（减少噪音）

- 服务区：展示状态点、名称、PID、快捷操作；命令细节默认隐藏。
- 日志区：展示“解释型输出”，工具细节和系统噪音降级。
- 任务区：突出优先级与阻塞，不铺满冗余字段。

## 五、数据与页面映射

- Dashboard：来自 `projects / tasks / sessions / project_services`
- 项目详情：来自 `project + tasks + project_services + recent_sessions`
- Session详情：来自 `session + session_events + session_summary`

# DevPilot 开发进度

> 最后更新: 2026-03-08

## 项目目标

**DevPilot** - AI 驱动的开发编排系统

核心功能：Agent 处理 Issue，实时查看输出，干预 Agent 行为，和它对话。

---

## 技术方案

| 方案 | 状态 | 问题 |
|------|------|------|
| tmux | ❌ 废弃 | 无法实时查看 Agent 输出 |
| 命令行调 claude | ❌ 废弃 | 无法干预 |
| Claude SDK | ⚠️ 当前 | 能看到输出，但无法对话 |
| json-stream | 🎯 目标 | 实现双向对话 |

---

## 当前进度

### 已完成
- [x] 前端框架：Dashboard、Projects、Project 详情、Issue 详情、Session 详情
- [x] 后端 API：projects、issues、sessions、workers、events
- [x] Worker 选择和 Session 启动
- [x] Session 实时输出显示（轮询 events）
- [x] 消息输入 UI（后端已实现真正的交互）
- [x] **agent-sdk 多轮对话后端实现**
- [x] 测试完整流程：验证多轮对话工作正常
- [x] **Agent Footer Prompt 配置**：保存在 config 表，发送给 Agent 前从库中读取

---

## 核心页面

| 路径 | 功能 |
|------|------|
| `/projects/[id]` | 项目详情：PRD、Issue、Workers 管理 |
| `/projects/[id]/issues/[issueId]` | Issue 详情：选择 Worker、启动 Session |
| `/projects/[id]/issues/[issueId]/sessions/[sessionId]` | Session 详情：实时输出、对话干预 |

---

## 关键文件

- 前端入口：`web/frontend/app/`
- 后端入口：`web/backend/main.py`
- Session 详情页：`web/frontend/app/projects/[id]/issues/[issueId]/sessions/[sessionId]/page.tsx`

---

## 教训

### 2026-03-08 上下文压缩灾难
- 问题：上下文压缩后，凭模糊记忆乱改代码
- 损失：项目详情页 718→222 行，Issue 详情页 618→262 行
- 恢复：通过 git history 恢复
- 预防：频繁提交、维护此文件

---

## 下一步

1. 测试恢复后的页面是否正常工作
2. 实现 json-stream 双向对话后端
3. 测试完整流程